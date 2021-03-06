import onmt

class Evaluator(object):
    def __init__(self, model, data, metrics, dicts, opt):
        self.model = model
        self.data = data
        self.loss_func = metrics["nmt_loss"]
        self.sent_reward_func = metrics["sent_reward"]
        self.corpus_reward_func = metrics["corp_reward"]
        self.dicts = dicts
        self.max_length = opt.max_predict_length

    def eval(self, pred_file=None):
        self.model.eval()

        total_loss = 0
        total_words = 0
        total_sents = 0
        total_sent_reward = 0

        all_preds = []
        all_targets = []
        for i in xrange(len(self.data)):
            # must be batch first for gather/scatter in DataParallel
            batch = self.data[i]
            targets = batch[1]

            outputs = self.model(batch, True)

            weights = targets.ne(onmt.Constants.PAD).float()
            num_words = weights.data.sum()
            _, loss = self.model.predict(outputs, targets, weights,
                self.loss_func)

            preds = self.model.translate(batch, self.max_length)
            preds = preds.t().tolist()
            targets = targets.data.t().tolist()
            rewards, _ = self.sent_reward_func(preds, targets)

            all_preds.extend(preds)
            all_targets.extend(targets)

            total_loss += loss
            total_words += num_words
            total_sent_reward += sum(rewards)
            total_sents += batch[0].size(1)

        loss = total_loss / total_words
        sent_reward = total_sent_reward / total_sents
        corpus_reward = self.corpus_reward_func(all_preds, all_targets)

        if pred_file is not None:
            self._convert_and_report(pred_file, all_preds,
                (loss, sent_reward, corpus_reward))

        return loss, sent_reward, corpus_reward

    def _convert_and_report(self, pred_file, preds, metrics):
        preds = self.data.restore_pos(preds)
        with open(pred_file, "w") as f:
            for sent in preds:
                sent = onmt.Reward.clean_up_sentence(sent, remove_unk=False,
                    remove_eos=True)
                sent = [self.dicts["tgt"].getLabel(w) for w in sent]
                print >> f, " ".join(sent)
        loss, sent_reward, corpus_reward = metrics
        print("")
        print("Loss: %.6f" % loss)
        print("Sentence reward: %.6f" % sent_reward)
        print("Corpus reward: %.6f" % corpus_reward)
        print("Predictions saved to %s" % pred_file)


