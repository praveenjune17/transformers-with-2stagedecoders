import shutil
import os
import tensorflow as tf
from utilities import create_tensorboard_parms

model_metrics = 'Step {},\n\
                 Train Loss {:.4f},\n\
                 train_BERT_F1 {},\n\
                 validation_perplexity {},\n\
                 validation_BERT_f1 {:.4f}\n'   
evaluation_step  = 'Time taken for {} step : {} secs' 
checkpoint_details = 'Saving checkpoint at step {} on {}'
(_, valid_output_sequence_writer, _) = create_tensorboard_parms()
aggregated_metric = tf.keras.metrics.Sum(name='weighted_and_unified_metric')

def train_sanity_check(tokenizer, predictions, target_id, log):
    
    prediction, target = next(iter(zip(predictions, target_id[:, :-1])))
    predicted = tokenizer.decode(tf.argmax(prediction,axis=-1), 
                                skip_special_tokens=True
                                )
    target = tokenizer.decode(target, 
                              skip_special_tokens=True
                              )
    log.info(f'target -> {target}')
    log.info(f'teacher forced predictions  -> {predicted}')

def training_results(
                    step,
                    train_loss,
                    train_BERT_score,
                    validation_perplexity, 
                    validation_bert_score,
                    timing_info,
                    ckpt_save_path,
                    log,
                    config
                    ):

      log.info(
                model_metrics.format(
                        step, 
                        train_loss,
                        train_BERT_score if config.show_BERT_F1_during_training else None,
                        validation_perplexity,
                        validation_bert_score*100 
                        )
              )
      log.info(evaluation_step.format(step, timing_info))
      log.info(checkpoint_details.format(step, ckpt_save_path))
      
def copy_checkpoint(copy_best_ckpt, ckpt_save_path, all_metrics, 
                    to_monitor, log, config):

    ckpt_fold, ckpt_string = os.path.split(ckpt_save_path)
    config.init_tolerance=0
    config.last_recorded_value =  all_metrics[to_monitor]
    ckpt_files_tocopy = [files for files in os.listdir(ckpt_fold) if ckpt_string in files if not 'temp' in files]
    ckpt_files_tocopy = ['checkpoint'] + ckpt_files_tocopy
    for files in ckpt_files_tocopy:
        shutil.copy2(os.path.join(ckpt_fold, files), config.best_ckpt_path)
    log.info(f'{to_monitor} is {all_metrics[to_monitor]:4f} so\
            {ckpt_string} is copied to best checkpoints directory')

def display_results(bert_score, perplexity, step, config):
    
    with valid_output_sequence_writer.as_default():
        tf.summary.scalar('BERT_f1', bert_score, step=step)
        tf.summary.scalar('Perplexity', perplexity, step=step)

def early_stop(train_loss, log, config, to_monitor):
    # Warn and early stop
    if config.init_tolerance > config.tolerance_threshold:
        log.warning('Tolerance exceeded')
        if config.early_stop:
            log.info(f'Early stopping since the {to_monitor} reached the tolerance threshold')
            return True
        else:
            return False
    else:
        return False
    # stop if minimum training loss is reached
    if train_loss < config.min_train_loss:
        log.warning(f'Minimum training loss reached')
        return True
    else:
        return False

def monitor_eval_metrics(ckpt_save_path,
                        perplexity,
                        bert_f1_score, 
                        train_loss,
                        step,
                        log,
                        config,
                        copy_best_ckpt=True):

    to_monitor=config.monitor_metric  
    all_eval_metrics = {
                        'bert_f1_score' : bert_f1_score, 
                        'perplexity' : perplexity
                        }
    assert to_monitor in all_eval_metrics, (
                  f'Available metrics to monitor are {all_eval_metrics}')
    aggregated_metric.reset_states()
    if config.run_tensorboard:
        display_results(all_eval_metrics['bert_f1_score'], 
                        all_eval_metrics['perplexity'],
                        step,
                        config)
    if to_monitor == 'bert_f1_score':
        copy_rule = (config.last_recorded_value <= all_eval_metrics[to_monitor])
    else:
        copy_rule = (config.last_recorded_value >= all_eval_metrics[to_monitor])
    if copy_rule:
        if copy_best_ckpt:
            copy_checkpoint(copy_best_ckpt, ckpt_save_path, 
                            all_eval_metrics, to_monitor, 
                            log, config)
        else:
            pass
    else:
        config.init_tolerance+=1

    return early_stop(train_loss, log, config, to_monitor)
