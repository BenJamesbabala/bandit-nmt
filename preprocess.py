import onmt

import argparse
import torch

parser = argparse.ArgumentParser(description="preprocess.lua")

##
## **Preprocess Options**
##

parser.add_argument("-config",    help="Read options from this file")

parser.add_argument("-train_src", required=True,
                    help="Path to the training source data")
parser.add_argument("-train_tgt", required=True,
                    help="Path to the training target data")

parser.add_argument("-train_xe_src", required=True,
                    help="Path to the training source data")
parser.add_argument("-train_xe_tgt", required=True,
                    help="Path to the training target data")

parser.add_argument("-train_pg_src", required=True,
                    help="Path to the training source data")
parser.add_argument("-train_pg_tgt", required=True,
                    help="Path to the training target data")


parser.add_argument("-valid_src", required=True,
                    help="Path to the validation source data")
parser.add_argument("-valid_tgt", required=True,
                     help="Path to the validation target data")
parser.add_argument("-test_src", default=None,
                    help="Path to the test source data")
parser.add_argument("-test_tgt", default=None,
                     help="Path to the test target data")


parser.add_argument("-save_data", required=True,
                    help="Output file for the prepared data")

parser.add_argument("-src_vocab_size", type=int, default=50000,
                    help="Size of the source vocabulary")
parser.add_argument("-tgt_vocab_size", type=int, default=50000,
                    help="Size of the target vocabulary")
parser.add_argument("-src_vocab",
                    help="Path to an existing source vocabulary")
parser.add_argument("-tgt_vocab",
                    help="Path to an existing target vocabulary")


parser.add_argument("-seq_length", type=int, default=50,
                    help="Maximum sequence length")
parser.add_argument("-shuffle",    type=int, default=1,
                    help="Shuffle data")
parser.add_argument("-seed",       type=int, default=3435,
                    help="Random seed")

parser.add_argument("-report_every", type=int, default=100000,
                    help="Report status every this many sentences")

opt = parser.parse_args()
torch.manual_seed(opt.seed)


def makeVocabulary(filename, size):
    vocab = onmt.Dict([onmt.Constants.PAD_WORD, onmt.Constants.UNK_WORD,
                       onmt.Constants.BOS_WORD, onmt.Constants.EOS_WORD])

    with open(filename) as f:
        for sent in f.readlines():
            for word in sent.split():
                vocab.add(word.lower())

    originalSize = vocab.size()
    vocab = vocab.prune(size)
    print("Created dictionary of size %d (pruned from %d)" %
          (vocab.size(), originalSize))

    return vocab


def initVocabulary(name, dataFile, vocabFile, vocabSize):

    vocab = None
    if vocabFile is not None:
        # If given, load existing word dictionary.
        print("Reading " + name + " vocabulary from \"" + vocabFile + "\"...")
        vocab = onmt.Dict()
        vocab.loadFile(vocabFile)
        print("Loaded " + str(vocab.size()) + " " + name + " words")

    if vocab is None:
        # If a dictionary is still missing, generate it.
        print("Building " + name + " vocabulary...")
        genWordVocab = makeVocabulary(dataFile, vocabSize)

        vocab = genWordVocab

    print()
    return vocab


def saveVocabulary(name, vocab, file):
    print("Saving " + name + " vocabulary to \"" + file + "\"...")
    vocab.writeFile(file)

def reorderSentences(pos, src, tgt, perm):
    new_pos = [pos[idx] for idx in perm]
    new_src = [src[idx] for idx in perm]
    new_tgt = [tgt[idx] for idx in perm]
    return new_pos, new_src, new_tgt

def makeData(which, srcFile, tgtFile, srcDicts, tgtDicts):
    src, tgt = [], []
    sizes = []
    count, ignored = 0, 0

    print("Processing %s & %s ..." % (srcFile, tgtFile))
    srcF = open(srcFile)
    tgtF = open(tgtFile)

    while True:
        srcWords = srcF.readline().split()
        tgtWords = tgtF.readline().split()

        if not srcWords or not tgtWords:
            if srcWords and not tgtWords or not srcWords and tgtWords:
                print("WARNING: source and target do not have the same number of sentences")
            break

        # Only remove long sentences for training set.
        if not ("train" in which and (len(srcWords) > opt.seq_length or \
            len(tgtWords) > opt.seq_length)):

            src += [srcDicts.convertToIdx(srcWords,
                                          onmt.Constants.UNK_WORD)]
            tgt += [tgtDicts.convertToIdx(tgtWords,
                                          onmt.Constants.UNK_WORD,
                                          eosWord=onmt.Constants.EOS_WORD)]

            sizes += [len(srcWords)]
        else:
            ignored += 1

        count += 1

        if count % opt.report_every == 0:
            print("... %d sentences prepared" % count)

    srcF.close()
    tgtF.close()

    assert len(src) == len(tgt)
    pos = range(len(src))

    if opt.shuffle == 1:
        print("... shuffling sentences")
        perm = torch.randperm(len(src))
        pos, src, tgt = reorderSentences(pos, src, tgt, perm)
        sizes = [sizes[idx] for idx in perm]

    print("... sorting sentences by size")
    _, perm = torch.sort(torch.Tensor(sizes))
    pos, src, tgt = reorderSentences(pos, src, tgt, perm)

    print("Prepared %d sentences (%d ignored due to length == 0 or > %d)" %
          (len(src), ignored, opt.seq_length))

    return src, tgt, pos


def makeDataGeneral(which, src_path, tgt_path, dicts):
    print("Preparing " + which + "...")
    res = {}
    res["src"], res["tgt"], res["pos"] = makeData(which, src_path, tgt_path,
        dicts["src"], dicts["tgt"])
    return res


def main():

    dicts = {}
    dicts["src"] = initVocabulary("source", opt.train_src, opt.src_vocab,
                                  opt.src_vocab_size)
    dicts["tgt"] = initVocabulary("target", opt.train_tgt, opt.tgt_vocab,
                                  opt.tgt_vocab_size)

    if opt.src_vocab is None:
        saveVocabulary("source", dicts["src"], opt.save_data + ".src.dict")
    if opt.tgt_vocab is None:
        saveVocabulary("target", dicts["tgt"], opt.save_data + ".tgt.dict")

    save_data = {}
    save_data["dicts"] = dicts
    save_data["train_xe"] = makeDataGeneral("train_xe", opt.train_xe_src,
        opt.train_xe_tgt, dicts)
    save_data["train_pg"] = makeDataGeneral("train_pg", opt.train_pg_src,
        opt.train_pg_tgt, dicts)
    save_data["valid"] = makeDataGeneral("valid", opt.valid_src, opt.valid_tgt,
        dicts)
    if opt.test_src is not None and opt.test_tgt is not None:
        save_data["test"] = makeDataGeneral("test", opt.test_src, opt.test_tgt,
            dicts)
    else:
        print("WARNING: test set not found!")

    print("Saving data to \"" + opt.save_data + "-train.pt\"...")
    torch.save(save_data, opt.save_data + "-train.pt")


if __name__ == "__main__":
    main()
