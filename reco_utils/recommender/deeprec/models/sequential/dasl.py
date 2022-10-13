# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import tensorflow as tf
import numpy as np
from reco_utils.recommender.deeprec.models.sequential.sli_rec import (
    SLI_RECModel,
)
from tensorflow.nn import dynamic_rnn
from reco_utils.recommender.deeprec.models.sequential.rnn_cell_implement import VecAttGRUCell
from reco_utils.recommender.deeprec.models.sequential.rnn_dien import dynamic_rnn as dynamic_rnn_dien
from reco_utils.recommender.deeprec.deeprec_utils import load_dict
from tensorflow.contrib.rnn import GRUCell, LSTMCell

__all__ = ["SASRecModel"]


class DASL(SLI_RECModel):

#      def _build_graph(self):
        #  """The main function to create sequential models.
        #
        #  Returns:
        #      obj:the prediction score make by the model.
        #  """
        #  hparams = self.hparams
        #  self.keep_prob_train = 1 - np.array(hparams.dropout)
        #  self.keep_prob_test = np.ones_like(hparams.dropout)
        #
        #  self.embedding_keep_prob_train = 1.0 - hparams.embedding_dropout
        #  if hparams.test_dropout:
        #      self.embedding_keep_prob_test = 1.0 - hparams.embedding_dropout
        #  else:
        #      self.embedding_keep_prob_test = 1.0
        #
        #  with tf.variable_scope("sequential") as self.sequential_scope:
        #      self._build_embedding()
        #      self._lookup_from_embedding()
        #      #  model_output = self._build_seq_graph()
        #      #  logit = self._fcn_net(model_output, hparams.layer_sizes, scope="logit_fcn")
        #      # for inner product
        #      logit = self._build_seq_graph()
        #      self._add_norm()
        #      return logit
#
    def _build_seq_graph(self, domain):
        """The main function to create sasrec model.
        
        Returns:
            obj:the output of sasrec section.
        """
        with tf.name_scope('sasrec'):
            self.seq = tf.concat(
                [self.item_history_embedding, self.cate_history_embedding], 2
            )
            # , 
            
            # self.seq = self.seq + self.position_embedding
            self.mask = self.iterator.mask
            self.real_mask = tf.cast(self.mask, tf.float32)
            self.sequence_length = tf.reduce_sum(self.mask, 1)

            #  attention_output = self._attention_fcn(self.target_item_embedding, hist_input)
            #  att_fea = tf.reduce_sum(attention_output, 1)
            # hyper-parameters
            self.dropout_rate = 0.0
            self.num_blocks = 1
            self.hidden_units = self.item_embedding_dim + self.cate_embedding_dim + self.user_embedding_dim
            self.num_heads = 1
            self.is_training = True
            #  self.recent_k = 5
            self.recent_k = 1

            # Dropout
            #  self.seq = tf.layers.dropout(self.seq,
                                         #  rate=self.dropout_rate,
                                         #  training=tf.convert_to_tensor(self.is_training))
            self.seq *= tf.expand_dims(self.real_mask, -1)
            reuse = False 
            if domain == "A":
                self.seq = tf.concat(
                    [self.seq, tf.tile(self.user_embedding_A, [1, self.sequence_length, 1])], 2
                )
                self.seq_A = tf.concat(
                    [self.item_history_embedding_A, self.cate_history_embedding_A], 2
                )
                self.seq_A = tf.concat(
                    [self.seq_A, tf.tile(self.user_embedding_A, [1, self.sequence_length, 1])], 2
                )
                # self.seq_A = self.seq_A + self.position_embedding_A
                # self.seq_A *= tf.expand_dims(self.real_mask, -1)
                # attention_output, alphas = self._attention_fcn(self.target_item_embedding, tf.concat([self.seq, self.seq_A], -1), 'Att_%s'%domain, False, return_alpha=True)


            else:
                self.seq = tf.concat(
                    [self.seq, tf.tile(self.user_embedding_B, [1, self.sequence_length, 1])], 2
                )
                reuse = True
                self.seq_B = tf.concat(
                    [self.item_history_embedding_B, self.cate_history_embedding_B], 2
                )
                self.seq_B = tf.concat(
                    [self.seq_B, tf.tile(self.user_embedding_B, [1, self.sequence_length, 1])], 2
                )
                # self.seq_B = self.seq_B + self.position_embedding_B
                # self.seq_B *= tf.expand_dims(self.real_mask, -1)
                # attention_output, alphas = self._attention_fcn(self.target_item_embedding, tf.concat([self.seq, self.seq_B], -1), 'Att_%s'%domain, False, return_alpha=True)

        with tf.variable_scope(domain,reuse=tf.AUTO_REUSE):
            if domain == "A":
                # output_1, _ = tf.nn.dynamic_rnn(GRUCell(hidden_size), inputs=self.seq_A, dtype=tf.float32)
                output_1, _ = dynamic_rnn(
                    GRUCell(self.hidden_units),
                    inputs=self.seq_A,
                    sequence_length=self.sequence_length,
                    dtype=tf.float32,
                    scope=domain,
                )
                # output_cross_2, _ = tf.nn.dynamic_rnn(GRUCell(hidden_size), inputs=self.seq, dtype=tf.float32)
                output_cross_2, _ = dynamic_rnn(
                    GRUCell(self.hidden_units),
                    inputs=self.seq,
                    sequence_length=self.sequence_length,
                    dtype=tf.float32,
                    scope=domain,
                )
            else:            
                # output_2, _ = tf.nn.dynamic_rnn(GRUCell(hidden_size), inputs=self.seq_B, dtype=tf.float32)
                output_2, _ = dynamic_rnn(
                    GRUCell(self.hidden_units),
                    inputs=self.seq_B,
                    sequence_length=self.sequence_length,
                    dtype=tf.float32,
                    scope=domain,
                )
                # output_cross_1, _ = tf.nn.dynamic_rnn(GRUCell(hidden_size), inputs=self.seq, dtype=tf.float32)
                output_cross_1, _ = dynamic_rnn(
                    GRUCell(self.hidden_units),
                    inputs=self.seq,
                    sequence_length=self.sequence_length,
                    dtype=tf.float32,
                    scope=domain,
                )
            # previous atte

        with tf.variable_scope('score_%s'%domain,reuse=tf.AUTO_REUSE): 
            if domain == "A":
                preference_1, _ = self.seq_attention(output_1, output_cross_1, self.hidden_units, self.sequence_length)
                preference_1 = tf.nn.dropout(preference_1, 0.1)
            else:
                preference_2, _ = self.seq_attention(output_2, output_cross_2, self.hidden_units, self.sequence_length)
                preference_2 = tf.nn.dropout(preference_2, 0.1)
        
        if domain == "A":
            self.hist_embedding_mean_A = tf.reduce_sum(self.seq_A*tf.expand_dims(self.real_mask, -1), 1)/tf.reduce_sum(self.real_mask, 1, keepdims=True)

            model_output = tf.concat([preference_1, self.target_item_embedding_A], -1)
            # model_output = tf.concat([preference_1, self.hist_embedding_mean_A], -1)
        #  import pdb; pdb.set_trace()
        else :
            self.hist_embedding_mean_B = tf.reduce_sum(self.seq_B*tf.expand_dims(self.real_mask, -1), 1)/tf.reduce_sum(self.real_mask, 1, keepdims=True)

            model_output = tf.concat([preference_2, self.target_item_embedding_B], -1)


        #  model_output = tf.concat([self.target_item_embedding, self.hist_embedding_concat], -1)
        #  model_output = self.hist_embedding_concat
        # Inner Product
        #  model_output = tf.reduce_sum(self.target_item_embedding * self.recent_embedding_mean, axis=-1)
        tf.summary.histogram("model_output_%s"%domain, model_output)
        # tf.summary.histogram("model_outputB", model_outputB)

        return model_output

    def normalize(self, inputs, 
                  epsilon = 1e-8,
                  scope="ln",
                  reuse=None):
        '''Applies layer normalization.
        
        Args:
          inputs: A tensor with 2 or more dimensions, where the first dimension has
            `batch_size`.
          epsilon: A floating number. A very small number for preventing ZeroDivision Error.
          scope: Optional scope for `variable_scope`.
          reuse: Boolean, whether to reuse the weights of a previous layer
            by the same name.
          
        Returns:
          A tensor with the same shape and data dtype as `inputs`.
        '''
        with tf.variable_scope(scope, reuse=reuse):
            inputs_shape = inputs.get_shape()
            params_shape = inputs_shape[-1:]
        
            mean, variance = tf.nn.moments(inputs, [-1], keep_dims=True)
            beta= tf.Variable(tf.zeros(params_shape))
            gamma = tf.Variable(tf.ones(params_shape))
            normalized = (inputs - mean) / ( (variance + epsilon) ** (.5) )
            outputs = gamma * normalized + beta
            
        return outputs

    def multihead_attention(self, queries, 
                            keys, 
                            num_units=None, 
                            num_heads=8, 
                            dropout_rate=0,
                            is_training=True,
                            causality=False,
                            scope="multihead_attention", 
                            reuse=None,
                            with_qk=False):
        '''Applies multihead attention.
        
        Args:
          queries: A 3d tensor with shape of [N, T_q, C_q].
          keys: A 3d tensor with shape of [N, T_k, C_k].
          num_units: A scalar. Attention size.
          dropout_rate: A floating point number.
          is_training: Boolean. Controller of mechanism for dropout.
          causality: Boolean. If true, units that reference the future are masked. 
          因果关系：布尔值。 如果为true，则屏蔽引用未来的单位。
          num_heads: An int. Number of heads.
          scope: Optional scope for `variable_scope`.
          reuse: Boolean, whether to reuse the weights of a previous layer
            by the same name.
            
        Returns
          A 3d tensor with shape of (N, T_q, C)  
        '''

        with tf.variable_scope(scope, reuse=reuse):
            # Set the fall back option for num_units
            if num_units is None:
                num_units = queries.get_shape().as_list[-1]
            
            # Linear projections
            # Q = tf.layers.dense(queries, num_units, activation=tf.nn.relu) # (N, T_q, C)
            # K = tf.layers.dense(keys, num_units, activation=tf.nn.relu) # (N, T_k, C)
            # V = tf.layers.dense(keys, num_units, activation=tf.nn.relu) # (N, T_k, C)
            if (scope.split('_')[0]=='groupConstruction'):
                queries = tf.tile(tf.expand_dims(queries, axis=0), [tf.shape(keys)[0], 1, 1])
            Q = tf.layers.dense(queries, num_units, activation=None) # (N, T_q, C)
            K = tf.layers.dense(keys, num_units, activation=None) # (N, T_k, C)
            V = tf.layers.dense(keys, num_units, activation=None) # (N, T_k, C)
            
            # Split and concat
            Q_ = tf.concat(tf.split(Q, num_heads, axis=2), axis=0) # (h*N, T_q, C/h) 
            K_ = tf.concat(tf.split(K, num_heads, axis=2), axis=0) # (h*N, T_k, C/h) 
            V_ = tf.concat(tf.split(V, num_heads, axis=2), axis=0) # (h*N, T_k, C/h) 

            # Multiplication
            outputs = tf.matmul(Q_, tf.transpose(K_, [0, 2, 1])) # (h*N, T_q, T_k)
            
            # Scale
            outputs = outputs / (K_.get_shape().as_list()[-1] ** 0.5)
            
            # Key Masking
            # tf.sign输出-1,0,1
            # 根据绝对值之和的符号判定是否mask，效果：某个sequence的特征全为0时（之前被mask过了），mask值为0，否则为1
            key_masks = tf.sign(tf.reduce_sum(tf.abs(keys), axis=-1)) # (N, T_k)
            key_masks = tf.tile(key_masks, [num_heads, 1]) # (h*N, T_k)
            key_masks = tf.tile(tf.expand_dims(key_masks, 1), [1, tf.shape(queries)[1], 1]) # (h*N, T_q, T_k)
            
            # 和下面query mask的区别：mask值不是设为0，而是设置为无穷小负值（原因是下一步要进行softmax，如果if不执行）
            paddings = tf.ones_like(outputs)*(-2**32+1)
            outputs = tf.where(tf.equal(key_masks, 0), paddings, outputs) # (h*N, T_q, T_k)
      
            # Causality = Future blinding
            if causality:
                # 构建下三角为1的tensor
                diag_vals = tf.ones_like(outputs[0, :, :]) # (T_q, T_k)
                tril = tf.linalg.LinearOperatorLowerTriangular(diag_vals).to_dense() # (T_q, T_k)
                masks = tf.tile(tf.expand_dims(tril, 0), [tf.shape(outputs)[0], 1, 1]) # (h*N, T_q, T_k)
       
                paddings = tf.ones_like(masks)*(-2**32+1)
                # 下三角置为无穷小负值（原因是下一步要进行softmax）
                outputs = tf.where(tf.equal(masks, 0), paddings, outputs) # (h*N, T_q, T_k)
      
            # Activation
            outputs = tf.nn.softmax(outputs) # (h*N, T_q, T_k)
             
            # Query Masking
            # tf.sign输出-1,0,1
            # 根据绝对值之和的符号判定是否mask，效果：某个sequence的特征全为0时（之前被mask过了），mask值为0，否则为1
            query_masks = tf.sign(tf.reduce_sum(tf.abs(queries), axis=-1)) # (N, T_q)
            query_masks = tf.tile(query_masks, [num_heads, 1]) # (h*N, T_q)
            query_masks = tf.tile(tf.expand_dims(query_masks, -1), [1, 1, tf.shape(keys)[1]]) # (h*N, T_q, T_k)
            outputs *= query_masks # broadcasting. (N, T_q, C)
              
            # Dropouts
            #  outputs = tf.layers.dropout(outputs, rate=dropout_rate, training=tf.convert_to_tensor(is_training))
                   
            # Weighted sum
            outputs = tf.matmul(outputs, V_) # ( h*N, T_q, C/h)
            
            # Restore shape
            outputs = tf.concat(tf.split(outputs, num_heads, axis=0), axis=2 ) # (N, T_q, C)
                  
            # Residual connection
            outputs += queries
                  
            # Normalize
            #outputs = normalize(outputs) # (N, T_q, C)
     
        if with_qk: return Q,K
        else: return outputs
    
    def feedforward(self, inputs, 
                    num_units=[2048, 512],
                    scope="multihead_attention", 
                    dropout_rate=0.2,
                    is_training=True,
                    reuse=None):
        '''Point-wise feed forward net.
        
        Args:
          inputs: A 3d tensor with shape of [N, T, C].
          num_units: A list of two integers.
          scope: Optional scope for `variable_scope`.
          reuse: Boolean, whether to reuse the weights of a previous layer
            by the same name.
            
        Returns:
          A 3d tensor with the same shape and dtype as inputs
        '''
        with tf.variable_scope(scope, reuse=reuse):
            # Inner layer
            params = {"inputs": inputs, "filters": num_units[0], "kernel_size": 1,
                      "activation": tf.nn.relu, "use_bias": True}
            outputs = tf.layers.conv1d(**params)
            #  outputs = tf.layers.dropout(outputs, rate=dropout_rate, training=tf.convert_to_tensor(is_training))
            # Readout layer
            params = {"inputs": outputs, "filters": num_units[1], "kernel_size": 1,
                      "activation": None, "use_bias": True}
            outputs = tf.layers.conv1d(**params)
            #  outputs = tf.layers.dropout(outputs, rate=dropout_rate, training=tf.convert_to_tensor(is_training))
            
            # Residual connection
            outputs += inputs
            
            # Normalize
            #outputs = normalize(outputs)
        
        return outputs

    def seq_attention(self, inputs, inputs_cross, hidden_size, attention_size):
        """
        Attention mechanism layer which reduces RNN/Bi-RNN outputs with Attention vector.
        The idea was proposed in the article by Z. Yang et al., "Hierarchical Attention Networks
        for Document Classification", 2016: http://www.aclweb.org/anthology/N16-1174.
        Variables notation is also inherited from the article
        """
        # Trainable parameters
        attention_size = attention_size * 2
        input_concat = tf.concat([inputs, inputs_cross],axis=1)
        w_omega = tf.Variable(tf.random_normal([hidden_size, attention_size], stddev=0.1))
        b_omega = tf.Variable(tf.random_normal([attention_size], stddev=0.1))
        u_omega = tf.Variable(tf.random_normal([attention_size], stddev=0.1))
        v = tf.tanh(tf.tensordot(input_concat, w_omega, axes=1) + b_omega)
        vu = tf.tensordot(v, u_omega, axes=1, name='vu')  # (B,T) shape
        alphas = tf.nn.softmax(vu, name='alphas')         # (B,T) shape
        alphas = tf.slice(alphas, [0,0], [self.batch_size, self.memory_window])
        # Output of (Bi-)RNN is reduced with attention vector; the result has (B,D) shape
        output = tf.reduce_sum(inputs * tf.tile(tf.expand_dims(alphas, -1), [1, 1, hidden_size]), 1, name="attention_embedding")
        return output, alphas
