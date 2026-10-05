# Bundled model notice

Crosshair Overlay includes `super-resolution-10.onnx` from the ONNX Model Zoo project, hosted at [onnxmodelzoo/super-resolution-10](https://huggingface.co/onnxmodelzoo/super-resolution-10).

- Upstream revision: `395472c`
- SHA-256: `85f36ff88cc504a24af5e0602148bc56a8aa09a58eca8c0da2756f3e8186035e`
- License: Apache-2.0, as declared by the model's Hugging Face model card; the license text is in `LICENSE-Apache-2.0.txt`.
- Model: Sub-pixel CNN Super Resolution, 3× luma enhancement. The worker converts RGB to YCbCr, resizes to 224×224, runs only the Y channel, bicubic-scales Cb/Cr, and converts back to RGB.
- Runtime: ONNX Runtime DirectML on supported hardware, with CPU fallback. Fast and Balanced modes never load the model.

This research model is optional Quality-mode processing. It can alter or invent pixels and is not a recovery of hidden scene detail. Its quality and latency vary by content; the in-repository synthetic benchmark is not evidence of improvement on all games.
