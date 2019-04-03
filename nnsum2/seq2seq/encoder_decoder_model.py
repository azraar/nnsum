from ..module import Module, register_module, hparam_registry
from nnsum.seq2seq.greedy_search import GreedySearch


@register_module("seq2seq.encoder_decoder_model")
class EncoderDecoderModel(Module):

    hparams = hparam_registry()

    @hparams()
    def encoder(self):
        pass

    @hparams()
    def decoder(self):
        pass

    def encode(self, inputs):
        encoder_output, encoder_state = self.encoder(
            inputs["source_input_features"], 
            inputs["source_lengths"])

        context = {"encoder_output": encoder_output,
                   "source_mask": inputs.get("source_mask", None),
                   "source_vocab_map": inputs.get("source_vocab_map", None),
                   "controls": inputs.get("controls", None)}
        return context, encoder_state

    def forward(self, inputs, encoded_inputs=None):

        if encoded_inputs is None:
            encoded_inputs = self.encode(inputs)

        context, encoder_state = encoded_inputs

        if "max_references" in inputs:
            context, encoder_state = self._expand_encoder_multiref(
                encoder_state, context, inputs["max_references"])

        return self.decoder(encoder_state,
                            inputs["target_input_features"], 
                            context,
                            None)

    def greedy_decode(self, batch, max_steps=300):
        context, encoder_state = self.encode(batch)
        return GreedySearch(self.decoder, encoder_state, context, 
                            max_steps=max_steps)

    def _expand_encoder_multiref(self, encoder_state, context, max_refs):
        steps, batch_size, _ = encoder_state.size()
        encoder_state = encoder_state\
            .unsqueeze(2).repeat(1, 1, max_refs, 1)\
            .view(steps, batch_size * max_refs, -1)

        encoder_output = context["encoder_output"]
        src_steps = context["encoder_output"].size(1)
        context["encoder_output"] = context["encoder_output"]\
            .unsqueeze(1).repeat(1, max_refs, 1, 1)\
            .view(batch_size * max_refs, src_steps, -1)
        
        src_mask = context.get("source_mask", None)
        if src_mask is not None:
            src_mask = src_mask.unsqueeze(1).repeat(1, max_refs, 1)\
                .view(batch_size * max_refs, -1)
            context["source_mask"] = src_mask
        
        src_vmap = context.get("source_vocab_map", None)
        if src_vmap is not None:
            steps = src_vmap.size(1)
            src_vmap = src_vmap.unsqueeze(1).repeat(1, max_refs, 1, 1)\
                .view(batch_size * max_refs, steps, -1) 
            context["source_vocab_map"] = src_vmap

        if context["controls"] is not None:
            raise Exception("Controls for multi-reference not implemented.")

        return context, encoder_state

    def initialize_parameters(self):
        self.encoder.initialize_parameters()
        self.decoder.initialize_parameters()

    def set_dropout(self, dropout):
        self.encoder.set_dropout(dropout)
        self.decoder.set_dropout(dropout)

        
