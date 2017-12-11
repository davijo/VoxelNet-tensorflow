#!/usr/bin/env python
# -*- coding:UTF-8 -*-

# File Name : train.py
# Purpose :
# Creation Date : 09-12-2017
# Last Modified : 2017年12月11日 星期一 20时23分27秒
# Created By : Jeasine Ma [jeasinema[at]gmail[dot]com]

import glob
import argparse
import os
import time
import tensorflow as tf
from itertools import count

from config import cfg
from model import RPN3D
from kitti_loader import KittiLoader


parser = argparse.ArgumentParser(description='training')
parser.add_argument('-i', '--max_epoch', type=int, nargs='?', default=10,
                    help='max epoch')
parser.add_argument('-n', '--tag', type=str, nargs='?', default='tag of this experiment',
                    help='set log tag')
parser.add_argument('-b', '--batch-size', type=int, nargs='?', default=1,
                    help='set batch size')
parser.add_argument('-l', '--lr', type=float, nargs='?', default=0.001,
                    help='set learning rate')
args = parser.parse_args()

dataset_dir = './data/object'
log_dir = os.path.join('./log', args.tag)
save_model_dir = os.path.join('./save_model', args.tag, 'checkpoint')


def main():
    # TODO: split file support
    with KittiLoader(object_dir=dataset_dir, queue_size=10, require_shuffle=True, 
            is_testset=False, batch_size=16, use_multi_process_num=8) as train_loader, \
         KittiLoader(object_dir=dataset_dir, queue_size=5, require_shuffle=True, 
            is_testset=False, batch_size=16, use_multi_process_num=8) as valid_loader :
        
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=cfg.GPU_MEMORY_FRACTION, 
            visible_device_list=cfg.GPU_AVAILABLE,
            allow_growth=True)
        config = tf.ConfigProto(
            gpu_options=gpu_options,
            device_count={
                "GPU" : cfg.GPU_USE_COUNT,  
            }
        )
        with tf.Session(config=config) as sess:
            model = RPN3D(
                cls=cfg.DETECT_OBJ,
                batch_size=args.batch_size,
                learning_rate=args.lr,
                max_gradient_norm=5.0,
                is_train=True,
                alpha=1.5,
                beta=1
            )
            # param init/restore
            save_model_dir = os.path.join(save_model_dir, args.tag, 'checkpoint')
            if tf.train.get_checkpoint_state(cpdir):
                print("Reading model parameters from %s" % save_model_dir)
                model.saver.restore(sess, tf.train.latest_checkpoint(save_model_dir))
            else:
                print("Created model with fresh parameters.")
                tf.global_variables_initializer().run()

            # train and validate
            iter_per_epoch = len(train_loader)/args.batch_size
            is_summary, is_summary_image, is_validate = False, False, False 
            
            summary_interval = 20
            summary_image_interval = 100
            save_model_interval = iter_in_epoch
            validate_interval = 200
            
            summary_writer = tf.summary.FileWriter(log_dir, sess.graph)
            while model.epoch.eval() < args.max_epoch:
                is_summary, is_summary_image, is_validate = False, False, False 
                iter = model.global_step.eval()
                if iter % summary_interval:
                    is_summary = True
                if iter % summary_image_interval:
                    is_summary_image = True 
                if iter % save_model_interval:
                    model.saver.save(sess, save_model_dir, global_step=model.global_step)
                if iter % validate_interval:
                    is_validate = True
                if iter % iter_per_epoch:
                    sess.run(model.epoch_add_op)
                    print('train {} epoch, total: {}'.format(model.epoch.eval(), args.max_epoch))

                ret = model.train_step(sess, train_loader.load(), train=True, summary=is_summary)

                if is_summary:
                    summary_writer.add_summary(ret[-1], iter)
            
                if is_summary_image:
                    ret = model.predict_step(sess, train_loader.load(), summary=True)
                    summary_writer.add_summary(ret[-1], iter)

                if is_validate:
                    ret = model.validate_step(sess, valid_loader.load(), summary=True)
                    summary_writer.add_summary(ret[-1], iter)
                
            print('train done. total epoch:{} iter:{}'.format(model.epoch.eval(), model.global_step.eval()))
            
            # finallly save model
            model.saver.save(sess, save_model_dir, global_step=model.global_step)

if __name__ == '__main__':
    main()
