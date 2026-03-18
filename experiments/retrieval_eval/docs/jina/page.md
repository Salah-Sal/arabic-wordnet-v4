Title: Embedding API

URL Source: https://jina.ai/embeddings

Published Time: Fri, 13 Mar 2026 01:58:12 GMT

Markdown Content:
Embedding API
===============

[![Image 1](https://jina.ai/Jina%20-%20Light.svg) * * * ![Image 2](https://jina.ai/Elastic%20-%20Light.svg)](https://jina.ai/)_search_ _reorder_

[News](https://jina.ai/news)[Models](https://jina.ai/models)

API

_keyboard\_arrow\_down_

Tokens Served

We served 9.3T tokens in last 30 days, 310.0B/day

* * *

[![Image 3](https://jina.ai/assets/reader-D06QTWF1.svg) Reader Convert any URL to Markdown for better grounding LLMs.](https://jina.ai/reader)[![Image 4](https://jina.ai/assets/embedding-DzEuY8_E.svg) Embeddings World-class multimodal multilingual embeddings.](https://jina.ai/embeddings)[![Image 5](https://jina.ai/assets/reranker-DudpN0Ck.svg) Reranker World-class reranker for maximizing search relevancy.](https://jina.ai/reranker)

[_![Image 6](blob:http://localhost/b78a1f382d77c37ecc505845c9fc4dcf)_ MCP](https://github.com/jina-ai/MCP)[_article_ llms.txt](https://jina.ai/models/llms.txt)[_smart\_toy_ Agents](https://docs.jina.ai/)[_data\_object_ Schema](https://api.jina.ai/openapi.json)[_child\_care_ Humans](https://api.jina.ai/scalar)

* * *

* * *

* * *

[Log in _login_](https://jina.ai/api-dashboard?login=true)

_language_

  

Theme

- [x] 

_routine_

 

Embeddings
==========

Top-performing multimodal multilingual long-context embeddings for search, RAG, agents applications.

_code_ API

* * *

_attach\_money_ Pricing

[Embedding API](https://jina.ai/embeddings)
-------------------------------------------

Try our world-class embedding models to improve your search and RAG systems. Start with a free trial!

_login_

_key_ API Key & Billing

_code_ Usage

_more\_horiz_ More

_chevron\_left_ _chevron\_right_

* * *

[_home_](https://jina.ai/embeddings)

[_speed_ Rate Limit](https://jina.ai/api-dashboard/rate-limit)

[_bug\_report_ Raise issue](https://huggingface.co/jinaai/undefined/discussions)

_cloud_ On CSP _arrow\_drop\_down_

[_help\_outline_ FAQ](https://jina.ai/embeddings#faq)

_menu\_book_ Docs _arrow\_drop\_down_

[Status](https://status.jina.ai/)

_chevron\_left_ _chevron\_right_

* * *

_![Image 7](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Select embeddings

_arrow\_drop\_down_

 

L2 normalization

Scale embeddings to unit length (L2 norm = 1). Required for cosine similarity via dot product.

- [x] 

 

Output data type

embedding_type

encoding_format

output_dtype

embedding_types

Choose output format: float (default), binary (compact storage), or base64 (efficient transmission).

Default (as float)

_arrow\_drop\_down_

 

 

* * *

Example input

Change them and see how the response changes!

_add_ Add

_delete_ Organic skincare for sensitive skin with aloe vera and chamomile: Imagine the soothing embrace of nature with our organic skincare range, crafted specifically for sensitive skin. Infused with the calming properties of aloe vera and chamomile, each product provides gentle nourishment and protection. Say goodbye to irritation and hello to a glowing, healthy complexion.
_delete_ Bio-Hautpflege für empfindliche Haut mit Aloe Vera und Kamille: Erleben Sie die wohltuende Wirkung unserer Bio-Hautpflege, speziell für empfindliche Haut entwickelt. Mit den beruhigenden Eigenschaften von Aloe Vera und Kamille pflegen und schützen unsere Produkte Ihre Haut auf natürliche Weise. Verabschieden Sie sich von Hautirritationen und genießen Sie einen strahlenden Teint.
_delete_ Cuidado de la piel orgánico para piel sensible con aloe vera y manzanilla: Descubre el poder de la naturaleza con nuestra línea de cuidado de la piel orgánico, diseñada especialmente para pieles sensibles. Enriquecidos con aloe vera y manzanilla, estos productos ofrecen una hidratación y protección suave. Despídete de las irritaciones y saluda a una piel radiante y saludable.
_delete_ 针对敏感肌专门设计的天然有机护肤产品：体验由芦荟和洋甘菊提取物带来的自然呵护。我们的护肤产品特别为敏感肌设计，温和滋润，保护您的肌肤不受刺激。让您的肌肤告别不适，迎来健康光彩。
_delete_ 新しいメイクのトレンドは鮮やかな色と革新的な技術に焦点を当てています: 今シーズンのメイクアップトレンドは、大胆な色彩と革新的な技術に注目しています。ネオンアイライナーからホログラフィックハイライターまで、クリエイティビティを解き放ち、毎回ユニークなルックを演出しましょう。

* * *

_upload_

Request

Bash

Language

_arrow\_drop\_down_

 

_wrap\_text_

```
curl https://api.jina.ai/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer " \
  -d @- <<EOFEOF
  {
    "normalized": true,
    "embedding_type": "float",
    "input": [
        "Organic skincare for sensitive skin with aloe vera and chamomile: Imagine the soothing embrace of nature with our organic skincare range, crafted specifically for sensitive skin. Infused with the calming properties of aloe vera and chamomile, each product provides gentle nourishment and protection. Say goodbye to irritation and hello to a glowing, healthy complexion.",
        "Bio-Hautpflege für empfindliche Haut mit Aloe Vera und Kamille: Erleben Sie die wohltuende Wirkung unserer Bio-Hautpflege, speziell für empfindliche Haut entwickelt. Mit den beruhigenden Eigenschaften von Aloe Vera und Kamille pflegen und schützen unsere Produkte Ihre Haut auf natürliche Weise. Verabschieden Sie sich von Hautirritationen und genießen Sie einen strahlenden Teint.",
        "Cuidado de la piel orgánico para piel sensible con aloe vera y manzanilla: Descubre el poder de la naturaleza con nuestra línea de cuidado de la piel orgánico, diseñada especialmente para pieles sensibles. Enriquecidos con aloe vera y manzanilla, estos productos ofrecen una hidratación y protección suave. Despídete de las irritaciones y saluda a una piel radiante y saludable.",
        "针对敏感肌专门设计的天然有机护肤产品：体验由芦荟和洋甘菊提取物带来的自然呵护。我们的护肤产品特别为敏感肌设计，温和滋润，保护您的肌肤不受刺激。让您的肌肤告别不适，迎来健康光彩。",
        "新しいメイクのトレンドは鮮やかな色と革新的な技術に焦点を当てています: 今シーズンのメイクアップトレンドは、大胆な色彩と革新的な技術に注目しています。ネオンアイライナーからホログラフィックハイライターまで、クリエイティビティを解き放ち、毎回ユニークなルックを演出しましょう。"
    ]
  }
EOFEOF
```

_content\_copy_

* * *

_send_ GET RESPONSE

* * *

_key_

API key

_visibility\_off_ _content\_copy_

* * *

Available tokens

0 _sync_

This is your unique key. Store it securely!

 

[v5-text: New SOTA Small Multilingual Embeddings](https://jina.ai/embeddings)
-----------------------------------------------------------------------------

jina-embeddings-v5-text delivers fifth-generation embedding quality in two efficient sizes — a 677M small and 239M nano model — with task-specific LoRA adapters, Matryoshka dimensions, 32K context, and GGUF/MLX quantization for edge deployment, setting new benchmarks across MMTEB, MTEB English, and retrieval tasks.

![Image 8](https://jina.ai/assets/v5-release-CDuEXOnC.gif)

[Read Release Note _arrow\_forward_](https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings)

[v4: Universal Embeddings for Multimodal Multilingual Retrieval](https://jina.ai/embeddings)
--------------------------------------------------------------------------------------------

jina-embeddings-v4 is our most significant leap yet — a 3.8B model that embeds text and images through a unified pathway, supporting both dense and late-interaction retrieval while outperforming proprietary models from Google, OpenAI and Voyage AI especially on visually rich document retrieval.

![Image 9](https://jina.ai/assets/Embeddings-v4-04-zkyAsjT9.gif)

[Two Ways to Purchase](https://jina.ai/embeddings#pricing)
----------------------------------------------------------

Subscribe to our API or purchase through cloud providers.

_radio\_button\_unchecked_

_cloud_

With **3** cloud service providers

Using AWS or Azure? You can deploy our models directly on your company's cloud platform and handle billing through the CSP account.

_![Image 10](https://jina.ai/assets/aws-\_fgBVdQm.svg)_ AWS SageMaker

_![Image 11](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Embeddings

_![Image 12](https://jina.ai/assets/reranker-DudpN0Ck.svg)_ Reranker

_![Image 13](blob:http://localhost/80ab35293a3a07b87f51f4a06f113c84)_ Microsoft Azure

_![Image 14](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Embeddings

_![Image 15](https://jina.ai/assets/reranker-DudpN0Ck.svg)_ Reranker

_![Image 16](blob:http://localhost/eb8eef1dd7c8e8e7a38cd1da22c52b42)_ Google Cloud

_![Image 17](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Embeddings

_radio\_button\_checked_

_![Image 18](https://jina.ai/J-active-light.svg)_

With Jina Search Foundation API

The easiest way to access all of our products. Top-up tokens as you go.

_content\_copy_

Enter the API key you wish to recharge

_error_

_visibility\_off_

 

Top up this API key with more tokens

Depending on your location, you may be charged in USD, EUR, or other currencies. Taxes may apply.

Please input the right API key to top up

Understand the rate limit

Rate limits are the maximum number of requests that can be made to an API within a minute per IP address/API key (RPM). Find out more about the rate limits for each product and tier below.

_keyboard\_arrow\_down_

Rate Limit

Rate limits are tracked in three ways: **RPM** (requests per minute), and **TPM** (tokens per minute). Limits are enforced per IP/API key and will be triggered when either the RPM or TPM threshold is reached first. When you provide an API key in the request header, we track rate limits by key rather than IP address.

Columns

_arrow\_drop\_down_

 

_fullscreen_

|  | Product | API Endpoint | Description _arrow\_upward_ | w/o API Key _key\_off_ | w/ Free API Key _key_ | w/ Paid API Key _key_ | w/ Premium API Key _key_ | Average Latency | Token Usage Counting | Allowed Request |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ![Image 19](https://jina.ai/assets/reader-D06QTWF1.svg) | Reader API | `https://r.jina.ai` | Convert URL to LLM-friendly text | 20 RPM | 500 RPM | 500 RPM | _trending\_up_ 5000 RPM | 7.9s | Count the number of tokens in the output response. | GET/POST |
| ![Image 20](https://jina.ai/assets/reader-D06QTWF1.svg) | Reader API | `https://s.jina.ai` | Search the web and convert results to LLM-friendly text | _block_ | 100 RPM | 100 RPM | _trending\_up_ 1000 RPM | 2.5s | Every request costs a fixed number of tokens, starting from 10000 tokens | GET/POST |
| ![Image 21](https://jina.ai/assets/embedding-DzEuY8_E.svg) | Embedding API | `https://api.jina.ai/v1/embeddings` | Convert text/images to fixed-length vectors | _block_ | 100 RPM & 100,000 TPM | 500 RPM & 2,000,000 TPM | _trending\_up_ 5,000 RPM & 50,000,000 TPM | _ssid\_chart_ depends on the input size _help_ | Count the number of tokens in the input request. | POST |
| ![Image 22](https://jina.ai/assets/reranker-DudpN0Ck.svg) | Reranker API | `https://api.jina.ai/v1/rerank` | Rank documents by query | _block_ | 100 RPM & 100,000 TPM | 500 RPM & 2,000,000 TPM | _trending\_up_ 5,000 RPM & 50,000,000 TPM | _ssid\_chart_ depends on the input size _help_ | Count the number of tokens in the input request. | POST |
| ![Image 23](blob:http://localhost/47430e9cbced04c539a17eb39573e3a9) | Classifier API | `https://api.jina.ai/v1/train` | Train a classifier using labeled examples | _block_ | 25 RPM & 25,000 TPM | 125 RPM & 500,000 TPM | 1,250 RPM & 12,000,000 TPM | _ssid\_chart_ depends on the input size | Tokens counted as: input_tokens × num_iters | POST |
| ![Image 24](blob:http://localhost/47430e9cbced04c539a17eb39573e3a9) | Classifier API (Few-shot) | `https://api.jina.ai/v1/classify` | Classify inputs using a trained few-shot classifier | _block_ | 25 RPM & 25,000 TPM | 125 RPM & 500,000 TPM | 1,250 RPM & 12,000,000 TPM | _ssid\_chart_ depends on the input size | Tokens counted as: input_tokens | POST |
| ![Image 25](blob:http://localhost/47430e9cbced04c539a17eb39573e3a9) | Classifier API (Zero-shot) | `https://api.jina.ai/v1/classify` | Classify inputs using zero-shot classification | _block_ | 25 RPM & 25,000 TPM | 125 RPM & 500,000 TPM | 1,250 RPM & 12,000,000 TPM | _ssid\_chart_ depends on the input size | Tokens counted as: input_tokens + label_tokens | POST |
| ![Image 26](blob:http://localhost/d9cb1deb4878909b05c9cd0f15af4aac) | Segmenter API | `https://api.jina.ai/v1/segment` | Tokenize and segment long text | 20 RPM | 200 RPM | 200 RPM | 1,000 RPM | 0.3s | Token is not counted as usage. | GET/POST |
| ![Image 27](blob:http://localhost/db267ccec0291b9762c00dd4567c6a5c) | DeepSearch | `https://deepsearch.jina.ai/v1/chat/completions` | Reason, search and iterate to find the best answer | _block_ | 50 RPM | 50 RPM | 500 RPM | 56.7s | Count the total number of tokens in the whole process. | POST |

Auto top-up on low token balance

Recommended for uninterrupted service in production. When your token balance drops below the set threshold, we will automatically recharge your saved payment method for the last purchased package, until the threshold is met.

_info_ We introduced a new pricing model on May 6th, 2025. If you enabled auto-recharge before this date, you'll continue to pay the old price (the one when you purchased). The new pricing only applies if you modify your auto-recharge settings or purchase a new API key.

_check_

< 1M Tokens

Top up when

_arrow\_drop\_down_

 

 

[On-premises deployment](https://jina.ai/embeddings)
----------------------------------------------------

Deploy Jina Embeddings models in AWS Sagemaker and Microsoft Azure, and soon in Google Cloud Services, or contact our sales team to get customized Kubernetes deployments for your Virtual Private Cloud and on-premises servers.

_![Image 28](https://jina.ai/assets/aws-\_fgBVdQm.svg)_ AWS SageMaker

_![Image 29](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Embeddings

_![Image 30](https://jina.ai/assets/reranker-DudpN0Ck.svg)_ Reranker

_![Image 31](blob:http://localhost/80ab35293a3a07b87f51f4a06f113c84)_ Microsoft Azure

_![Image 32](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Embeddings

_![Image 33](https://jina.ai/assets/reranker-DudpN0Ck.svg)_ Reranker

_![Image 34](blob:http://localhost/eb8eef1dd7c8e8e7a38cd1da22c52b42)_ Google Cloud

_![Image 35](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Embeddings

![Image 36](https://jina.ai/assets/pattern-developers-DbqNZCU0.svg)

[API Integrations](https://jina.ai/embeddings)

Our Embedding API is natively integrated with various renowned databases, vector stores, RAG, and LLMOps frameworks. To begin, just copy and paste your API key into any of the listed integrations for a quick and seamless start.

Vector Store

LLMOps

RAG

Observability

_open\_in\_new_

![Image 37](blob:http://localhost/5d4fd576e1a99efcf818b6400f55ea0c)

MongoDB

_open\_in\_new_

![Image 38](blob:http://localhost/711c5e97e31a01671dc4cd90f6fb481c)

DataStax

_open\_in\_new_

![Image 39](blob:http://localhost/15e045ccedc0716dbfd6cb5eef7ff23e)

Qdrant

_open\_in\_new_

![Image 40](blob:http://localhost/7c760bc7c0ad6e8413170ff55f5a06c3)

Pinecone

_open\_in\_new_

![Image 41](blob:http://localhost/8fd1ae510a407f283ecef750fb5fdb5c)

Chroma

_open\_in\_new_

![Image 42](https://jina.ai/assets/icon-Weaviate-CfbkPZsU.svg)

Weaviate

_open\_in\_new_

![Image 43](https://jina.ai/assets/icon-Milvus-Bz_cf8R2.png)

Milvus

_open\_in\_new_

![Image 44](https://jina.ai/assets/icon-Epsilla-BPYuTwuZ.png)

Epsilla

_open\_in\_new_

![Image 45](blob:http://localhost/a642d726a6a7acaf3fe5c1a1f0063602)

MyScale

_open\_in\_new_

![Image 46](https://jina.ai/assets/icon-LlamaIndex-CKyGrd9a.png)

LlamaIndex

_open\_in\_new_

![Image 47](blob:http://localhost/fa7c060a926af05a1ae3316f9c3979ac)

Haystack

_open\_in\_new_

![Image 48](https://jina.ai/assets/icon-Langchain-hPS1w007.png)

Langchain

_open\_in\_new_

![Image 49](https://jina.ai/assets/icon-Dify-BQetVg9h.png)

Dify

_open\_in\_new_

![Image 50](blob:http://localhost/66f3050f2532ed18edfe6d12c392a6c9)

SuperDuperDB

_open\_in\_new_

![Image 51](blob:http://localhost/ce800717ee71b3902219b63e7d353940)

DashVector

_open\_in\_new_

![Image 52](https://jina.ai/assets/icon-portkey-BY2A2xDT.png)

Portkey

_open\_in\_new_

![Image 53](blob:http://localhost/662c92214f72a6bbc15b22775f0cf6a6)

Baseten

_open\_in\_new_

![Image 54](https://jina.ai/assets/icon-tidb-vhSazXAM.png)

TiDB

_open\_in\_new_

![Image 55](https://jina.ai/assets/icon-lancedb-r57HMIMm.png)

LanceDB

_open\_in\_new_

![Image 56](https://jina.ai/assets/icon-carbon-ERjBNjcr.svg)

Carbon

[Our Publications](https://jina.ai/embeddings)
----------------------------------------------

Understand how our frontier search models were trained from scratch, check out our latest publications. Meet our team at EMNLP, SIGIR, ICLR, NeurIPS, and ICML!

[![Image 57: jina-embeddings-v5-text: Task-Targeted Embedding Distillation](https://jina.ai/assets/paper-19-DFP5VMOX.webp) _![Image 58](https://jina.ai/arxiv\_logo.svg)_ arXiv February 17, 2026 jina-embeddings-v5-text: Task-Targeted Embedding Distillation](https://arxiv.org/abs/2602.15547)[![Image 59](https://jina.ai/assets/paper-18-Dt9UWxtF.webp) _![Image 60](https://jina.ai/arxiv\_logo.svg)_ arXiv February 11, 2026 Embedding Inversion via Conditional Masked Diffusion Language Models](https://arxiv.org/abs/2602.11047)[![Image 61](https://jina.ai/assets/paper-17-B5A4jouC.webp) ICLR 2026 January 22, 2026 Embedding Compression via Spherical Coordinates](https://arxiv.org/abs/2602.00079)[![Image 62](https://jina.ai/assets/paper-16-B2-c2xJU.webp) _![Image 63](https://jina.ai/arxiv\_logo.svg)_ arXiv December 29, 2025 Vision Encoders in Vision-Language Models: A Survey](https://jina.ai/vision-encoder-survey.pdf)[![Image 64](https://jina.ai/assets/paper-15-w4iG1e4r.webp) ICLR 2026 December 04, 2025 Jina-VLM: Small Multilingual Vision Language Model](https://arxiv.org/abs/2512.04032)[![Image 65](https://jina.ai/assets/paper-14-DExN25vZ.webp) AAAI 2026 October 01, 2025 jina-reranker-v3: Last but Not Late Interaction for Document Reranking](https://arxiv.org/abs/2509.25085)[![Image 66](https://jina.ai/assets/paper-13-4R1ByXdX.webp) NeurIPS 2025 August 31, 2025 Efficient Code Embeddings from Code Generation Models](https://arxiv.org/abs/2508.21290)[![Image 67](https://jina.ai/assets/paper-12-BkD-63lO.webp) EMNLP 2025 June 24, 2025 jina-embeddings-v4: Universal Embeddings for Multimodal Multilingual Retrieval](https://arxiv.org/abs/2506.18902)[![Image 68](https://jina.ai/assets/paper-11-CEUlDi35.webp) ICLR 2025 March 04, 2025 ReaderLM-v2: Small Language Model for HTML to Markdown and JSON](https://arxiv.org/abs/2503.01151)[![Image 69](https://jina.ai/assets/paper-10-BVjrGETf.webp) ACL 2025 December 17, 2024 AIR-Bench: Automated Heterogeneous Information Retrieval Benchmark](https://arxiv.org/abs/2412.13102)[![Image 70](https://jina.ai/assets/paper-9-C7WsuRkA.webp) ICLR 2025 December 12, 2024 jina-clip-v2: Multilingual Multimodal Embeddings for Text and Images](https://arxiv.org/abs/2412.08802)[![Image 71](https://jina.ai/assets/paper-8-B_zo2lUJ.webp) ECIR 2025 September 18, 2024 jina-embeddings-v3: Multilingual Embeddings With Task LoRA](https://arxiv.org/abs/2409.10173)[![Image 72](https://jina.ai/assets/paper-7-CjzUhm3a.webp) SIGIR 2025 September 07, 2024 Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models](https://arxiv.org/abs/2409.04701)[![Image 73](https://jina.ai/assets/paper-6-BhUOK5kt.webp) EMNLP 2024 August 30, 2024 Jina-ColBERT-v2: A General-Purpose Multilingual Late Interaction Retriever](https://arxiv.org/abs/2408.16672)[![Image 74](https://jina.ai/assets/paper_5-SY9hRgw7.webp) WWW 2025 June 21, 2024 Leveraging Passage Embeddings for Efficient Listwise Reranking with Large Language Models](https://arxiv.org/abs/2406.14848)[![Image 75](https://jina.ai/assets/paper_4-Docs_rL4.webp) ICML 2024 May 30, 2024 Jina CLIP: Your CLIP Model Is Also Your Text Retriever](https://arxiv.org/abs/2405.20204)[![Image 76](https://jina.ai/assets/paper_3-C-S8VDHs.webp) _![Image 77](https://jina.ai/arxiv\_logo.svg)_ arXiv February 26, 2024 Multi-Task Contrastive Learning for 8192-Token Bilingual Text Embeddings](https://arxiv.org/abs/2402.17016)[![Image 78](https://jina.ai/assets/paper_1-C_6EYPFN.webp) _![Image 79](https://jina.ai/arxiv\_logo.svg)_ arXiv October 30, 2023 Jina Embeddings 2: 8192-Token General-Purpose Text Embeddings for Long Documents](https://arxiv.org/abs/2310.19923)[![Image 80](https://jina.ai/assets/paper_2-BcVWvZK_.webp) EMNLP 2023 July 20, 2023 Jina Embeddings: A Novel Set of High-Performance Sentence Embedding Models](https://arxiv.org/abs/2307.11224)

19 publications in total.

[Learning about Embeddings](https://jina.ai/embeddings)
-------------------------------------------------------

Where to start with embeddings? We've got you covered. Learn about embeddings from the ground up with our comprehensive guide.

[![Image 81: Abstract illustration of a sound wave or heartbeat, formed by blue, orange, and gray dots on a white background.](https://jina.ai/blog-banner/bootstrapping-audio-embeddings-from-multimodal-llms.gif) March 11, 2026 • 7 minutes read Bootstrapping Audio Embeddings from Multimodal LLMs Turn any multimodal LLM into a small audio embedding model that beats CLAP with 25x less data. ![Image 82: Han Xiao](https://jina-ai-gmbh.ghost.io/content/images/2022/10/Untitled-2.png)](https://jina.ai/news/bootstrapping-audio-embeddings-from-multimodal-llms)

[![Image 83: Fingerprint illustration made from numbers, showcasing digital and high-tech design on a light background.](https://jina.ai/blog-banner/identifying-embedding-models-from-raw-numerical-values.gif) March 06, 2026 • 6 minutes read Identifying Embedding Models from Raw Numerical Values A tiny transformer that fingerprints embedding models by reading raw numerical digits. No feature engineering. ![Image 84: Han Xiao](https://jina-ai-gmbh.ghost.io/content/images/2022/10/Untitled-2.png)](https://jina.ai/news/identifying-embedding-models-from-raw-numerical-values)

[![Image 85: Abstract digital artwork in black and white, featuring scattered dots forming letters in a halftone effect. The central lette](https://jina.ai/blog-banner/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings.gif) February 19, 2026 • 7 minutes read jina-embeddings-v5-text: New SOTA Small Multilingual Embeddings Two sub-1B multilingual embeddings with best-in-class performance, available on Elastic Inference Service, Llama.cpp and MLX. ![Image 86: Han Xiao](https://jina-ai-gmbh.ghost.io/content/images/2022/10/Untitled-2.png)](https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings)

[![Image 87: jina-embeddings-v5-text: Task-Targeted Embedding Distillation](https://jina.ai/assets/paper-19-DFP5VMOX.webp) February 17, 2026 jina-embeddings-v5-text: Task-Targeted Embedding Distillation Text embedding models are widely used for semantic similarity tasks, including information retrieval, clustering, and classification. General-purpose models are typically trained with single- or multi-stage processes using contrastive loss functions. We introduce a novel training regimen that combines model distillation techniques with task-specific contrastive loss to produce compact, high-performance embedding models. Our findings suggest that this approach is more effective for training small models than purely contrastive or distillation-based training paradigms alone. Benchmark scores for the resulting models, jina-embeddings-v5-text-small and jina-embeddings-v5-text-nano, exceed or match the state-of-the-art for models of similar size. jina-embeddings-v5-text models additionally support long texts (up to 32k tokens) in many languages, and generate embeddings that remain robust under truncation and binary quantization. Model weights are publicly available, hopefully inspiring further advances in embedding model development.](https://arxiv.org/abs/2602.15547)

_circle_ _circle_ _circle_ _circle_ _circle_ _circle_ _circle_ _circle_ _circle_ _circle_ _circle_ _circle_

[Comparison of Reranker, Vector Search, and BM25](https://jina.ai/embeddings)
-----------------------------------------------------------------------------

The table below provides a comprehensive comparison of the Reranker, Vector/Embeddings Search, and BM25, highlighting their strengths and weaknesses across various categories.

|  | Reranker | Vector Search | BM25 |
| --- | --- | --- | --- |
| **Best For** | Enhanced search precision and relevance | Initial, rapid filtering | General text retrieval across wide-ranging queries |
| **Granularity** | Detailed: Sub-document and query segment | Broad: Entire documents | Intermediate: Various text segments |
| **Query Time Complexity** | High | Medium | Low |
| **Indexing Time Complexity** | Not required | High | Low, utilizes pre-built index |
| **Training Time Complexity** | High | High | Not required |
| **Search Quality** | Superior for nuanced queries | Balanced between efficiency and accuracy | Consistent and reliable for a broad set of queries |
| **Strengths** | Highly accurate with deep contextual understanding | Quick and efficient, with moderate accuracy | Highly scalable, with established efficacy |
|  | [_![Image 88](https://jina.ai/assets/reranker-DudpN0Ck.svg)_ Try reranker API for free](https://jina.ai/reranker) | [_![Image 89](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_ Try embedding API for free](https://jina.ai/embeddings) |  |

[The Evolution of Embeddings Poster](https://jina.ai/embeddings)
----------------------------------------------------------------

Discover the ideal poster for your space, featuring captivating infographics or breathtaking visuals tracing the evolution of text embedding models since 1950.

[Learn how we made it](https://jina.ai/news/the-1950-2024-text-embeddings-evolution-poster)

* * *

[_shopping\_cart_ Buy a hard copy](https://buy.stripe.com/cN2aHS4Ax5F19DqfZ7)

![Image 90](https://jina.ai/assets/oVA1TLlM6Vy-DuY9hhF-.png)

[FAQ](https://jina.ai/embeddings#faq)
-------------------------------------

_![Image 91](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

How were the Jina embedding models trained?

_keyboard\_arrow\_down_

For detailed information on our training processes, data sources, and evaluations, please refer to our technical reports on arXiv for `jina-embeddings-v3` and `jina-embeddings-v4`.

[_launch_ arXiv](https://arxiv.org/abs/2409.10173)

_![Image 92](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What are your multimodal embedding models?

_keyboard\_arrow\_down_

`jina-embeddings-v4` is our latest universal multimodal model (3.8B parameters) supporting text and images with 32K context, dense and late-interaction retrieval, and SOTA performance on visually rich documents. `jina-clip-v2` is a lighter option (865M parameters) supporting 89 languages with 512x512 image resolution and Matryoshka representations. Both excel at text-text, text-image, and image-image retrieval tasks.

[_launch_ arXiv](https://arxiv.org/abs/2412.08802)

_![Image 93](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Which languages do your models support?

_keyboard\_arrow\_down_

Both `jina-embeddings-v4` and `jina-embeddings-v3` support 89 languages with strong multilingual performance. The top 30 languages include: Arabic, Bengali, Chinese, Danish, Dutch, English, Finnish, French, Georgian, German, Greek, Hindi, Indonesian, Italian, Japanese, Korean, Latvian, Norwegian, Polish, Portuguese, Romanian, Russian, Slovak, Spanish, Swedish, Thai, Turkish, Ukrainian, Urdu, and Vietnamese. `jina-clip-v2` also supports 89 languages for multimodal tasks.

[_launch_ arXiv](https://arxiv.org/abs/2409.10173)

_![Image 94](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What is the maximum length for a single sentence input?

_keyboard\_arrow\_down_

Context length varies by model: `jina-embeddings-v4` supports up to 32K tokens, while `jina-embeddings-v3` and `jina-clip-v2` support up to 8192 tokens. A token can range from a single character to an entire word. This extended context enables comprehensive document analysis and higher accuracy in context understanding for extensive textual data.

_![Image 95](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What is the maximum number of sentences I can include in a single request?

_keyboard\_arrow\_down_

There is no hard limit on the number of items per request. The API batches inputs internally by token count for optimal GPU utilization. You can send as many texts or images as needed in a single request.

_![Image 96](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

How do I send images to multimodal embedding models?

_keyboard\_arrow\_down_

For `jina-embeddings-v4`, `jina-clip-v2`, and `jina-clip-v1`, you can use either `url` or `bytes` in the `input` field of the API request. For `url`, provide the URL of the image you want to process. For `bytes`, encode the image in base64 format. `jina-embeddings-v4` can also directly embed PDF documents by passing a PDF URL or base64-encoded PDF bytes.

_![Image 97](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

How do Jina Embeddings models compare to OpenAI's and Cohere's latest embeddings?

_keyboard\_arrow\_down_

`jina-embeddings-v4` is our latest flagship model achieving SOTA on visually rich document retrieval (ViDoRe) and multimodal benchmarks. For text-only tasks, `jina-embeddings-v3` outperforms OpenAI and Cohere on MTEB English and Multilingual benchmarks while being smaller and more efficient. Both models support Matryoshka Representation Learning (MRL) allowing dimension truncation (down to 32 for v3, down to 128 for v4) without significant performance loss.

_![Image 98](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

How seamless is the transition from OpenAI's text-embedding-3-large to your solution?

_keyboard\_arrow\_down_

The transition is streamlined, as [our API endpoint](https://api.jina.ai/v1/embeddings), matches the input and output JSON schemas of OpenAI’s `text-embedding-3-large` model. This compatibility ensures users can easily replace the OpenAI model with ours when using OpenAI’s endpoint.

_![Image 99](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

How tokens are calculated when using jina-clip and jina-embeddings models?

_keyboard\_arrow\_down_

Tokens are calculated based on the text length and image size. For text in the request, tokens are counted in the standard way. For images, the following steps are conducted: 1. Tile Size: Each image is divided into tiles. For `jina-embeddings-v4`, tiles are 28x28 pixels, for `jina-clip-v2`, tiles are 512x512 pixels, while for `jina-clip-v1`, tiles are 224x224 pixels. 2. Coverage: The number of tiles required to cover the input image is calculated. Even if the image dimensions are not perfectly divisible by the tile size, partial tiles are counted as full tiles. 3. Total Tiles: The total number of tiles covering the image determines the cost. For example, a 600x600 pixel image would be covered by 22x22 tiles (484 tiles) in jina-embeddings-v4, by 2x2 tiles (4 tiles) in jina-clip-v2 and 3x3 tiles (9 tiles) in jina-clip-v1. 4. Cost Calculation: For `jina-embeddings-v4`, each tile costs 10 tokens, for `jina-clip-v2`, each tile costs 4000 tokens, while for `jina-clip-v1`, each tile costs 1000 tokens. Example: For an image with dimensions 600x600 pixels: • With `jina-embeddings-v4` • The image is divided into 28x28 pixel tiles. • The total number of tiles required is 22 (horizontal) x 22 (vertical) = 484 tiles. • The cost for `jina-embeddings-v4` will be 484*10 = 4840 tokens. • With `jina-clip-v2` • The image is divided into 512x512 pixel tiles. • The total number of tiles required is 2 (horizontal) x 2 (vertical) = 4 tiles. • The cost for `jina-clip-v2` will be 4*4000 = 16000 tokens. • With `jina-clip-v1` • The image is divided into 224x224 pixel tiles. • The total number of tiles required is 3 (horizontal) x 3 (vertical) = 9 tiles. • The cost for jina-clip-v1 will be 9*1000 = 9000 tokens.

_![Image 100](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Do you provide models for embedding images or audio?

_keyboard\_arrow\_down_

Yes, `jina-embeddings-v4`, `jina-clip-v2` and `jina-clip-v1` can embed both images and texts. Embedding models on more modalities will be announced soon!

_![Image 101](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Can Jina Embedding models be fine-tuned with private or company data?

_keyboard\_arrow\_down_

For inquiries about fine-tuning our models with specific data, please contact us to discuss your requirements. We are open to exploring how our models can be adapted to meet your needs.

[Contact](https://jina.ai/contact-sales)

_![Image 102](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Can your endpoints be hosted privately on AWS, Azure, or GCP?

_keyboard\_arrow\_down_

Yes, our services are available on AWS, Azure, and GCP marketplaces. If you have specific requirements, please contact us at sales AT jina.ai.

[_launch_ AWS SageMaker](https://aws.amazon.com/marketplace/seller-profile?id=seller-stch2ludm6vgy)[_launch_ Google Cloud](https://console.cloud.google.com/marketplace/browse?q=jina&pli=1&inv=1&invt=AbmydQ)[_launch_ Microsoft Azure](https://azuremarketplace.microsoft.com/en-US/marketplace/apps?page=1&search=jina)

_![Image 103](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What is the 'task' parameter and when should I use it?

_keyboard\_arrow\_down_

The `task` parameter in `jina-embeddings-v3` and `jina-embeddings-v4` activates task-specific LoRA adapters for optimal performance. Use `retrieval.query` for search queries, `retrieval.passage` for documents to be searched, `text-matching` for semantic similarity, `classification` for text classification, and `separation` for clustering tasks.

_![Image 104](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What is late-interaction retrieval and which models support it?

_keyboard\_arrow\_down_

`jina-embeddings-v4` supports both dense (single-vector) and late-interaction (multi-vector) retrieval via the `output_type` parameter. Late-interaction preserves more fine-grained token-level information for higher retrieval accuracy on complex queries. `jina-colbert-v2` is a dedicated late-interaction model.

_![Image 105](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What is late chunking and when should I use it?

_keyboard\_arrow\_down_

Late chunking is a technique that embeds the entire document first using long-context models, then extracts chunk embeddings from the token-level representations. Unlike naive chunking (chunk first, then embed), late chunking preserves cross-chunk context, improving retrieval for RAG applications. Enable it via the `late_chunking` parameter in `jina-embeddings-v3`.

_![Image 106](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Why does the API support a different context length than the model's maximum capacity?

_keyboard\_arrow\_down_

While some of our embedding models are architecturally capable of processing longer context lengths, the API may enforce lower limits due to GPU VRAM constraints in our inference infrastructure. Processing very long sequences requires substantial memory, and we optimize our serving configuration to balance throughput, latency, and cost for the majority of use cases. If you require extended context length support, please contact our sales team to discuss dedicated deployment options.

_![Image 107](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

Why is jina-embeddings-v4 free, and why is it slow?

_keyboard\_arrow\_down_

`jina-embeddings-v4` is built on the Qwen2-VL base model, which is released under the Qwen Research License. This license permits research and non-commercial use only, meaning we cannot offer `jina-embeddings-v4` as a commercial product. As a result, we provide access to the model free of charge via our API. There are two reasons why `jina-embeddings-v4` may appear slower than other models: First, `jina-embeddings-v4` is a significantly larger model than `jina-embeddings-v3`, so it inherently requires more computation time per request. Second, because we cannot commercialize this model, we intentionally throttle API throughput to manage infrastructure costs. Users should not expect high-volume or production-level throughput when using the `jina-embeddings-v4` API. For production workloads requiring higher throughput, we recommend using `jina-embeddings-v3` or deploying `jina-embeddings-v4` on your own infrastructure via Hugging Face.

_![Image 108](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What are the rate limits for the Embeddings API?

_keyboard\_arrow\_down_

Rate limits depend on your API key type:

**Free:** 100 RPM, 100K TPM, 2 concurrent requests

**Paid:** 500 RPM, 2M TPM, 50 concurrent requests

**Premium:** 5,000 RPM, 50M TPM, 500 concurrent requests

Additionally, there is an IP-based rate limit of 10,000 requests per 60 seconds to prevent abuse. If you need higher limits, please contact our sales team.

_![Image 109](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What are the context length limits for each embedding model?

_keyboard\_arrow\_down_

Each model has a maximum context length per input:

**jina-embeddings-v4:** 32,768 tokens

**jina-embeddings-v3:** 8,192 tokens

**jina-embeddings-v2-*:** 8,192 tokens

**jina-clip-v1/v2:** 8,192 tokens

**jina-colbert-v1/v2:** 8,192 tokens

**jina-code-embeddings-*:** 32,768 tokens

Inputs exceeding the limit will return an error unless `truncate: true` is set, which automatically truncates to the maximum length.

_![Image 110](https://jina.ai/assets/embedding-DzEuY8\_E.svg)_

What are the file size limits for images and PDFs?

_keyboard\_arrow\_down_

Maximum file sizes are: **Images:** 5 MB, **PDFs:** 8 MB. Larger files will be rejected with an error.

### [How to get my API key?](https://jina.ai/embeddings#get-api-key)

 video_not_supported

### [What's the rate limit?](https://jina.ai/embeddings#rate-limit)

Rate Limit

Rate limits are tracked in three ways: **RPM** (requests per minute), and **TPM** (tokens per minute). Limits are enforced per IP/API key and will be triggered when either the RPM or TPM threshold is reached first. When you provide an API key in the request header, we track rate limits by key rather than IP address.

Columns

_arrow\_drop\_down_

 

_fullscreen_

|  | Product | API Endpoint | Description _arrow\_upward_ | w/o API Key _key\_off_ | w/ Free API Key _key_ | w/ Paid API Key _key_ | w/ Premium API Key _key_ | Average Latency | Token Usage Counting | Allowed Request |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ![Image 111](https://jina.ai/assets/reader-D06QTWF1.svg) | Reader API | `https://r.jina.ai` | Convert URL to LLM-friendly text | 20 RPM | 500 RPM | 500 RPM | _trending\_up_ 5000 RPM | 7.9s | Count the number of tokens in the output response. | GET/POST |
| ![Image 112](https://jina.ai/assets/reader-D06QTWF1.svg) | Reader API | `https://s.jina.ai` | Search the web and convert results to LLM-friendly text | _block_ | 100 RPM | 100 RPM | _trending\_up_ 1000 RPM | 2.5s | Every request costs a fixed number of tokens, starting from 10000 tokens | GET/POST |
| ![Image 113](https://jina.ai/assets/embedding-DzEuY8_E.svg) | Embedding API | `https://api.jina.ai/v1/embeddings` | Convert text/images to fixed-length vectors | _block_ | 100 RPM & 100,000 TPM | 500 RPM & 2,000,000 TPM | _trending\_up_ 5,000 RPM & 50,000,000 TPM | _ssid\_chart_ depends on the input size _help_ | Count the number of tokens in the input request. | POST |
| ![Image 114](https://jina.ai/assets/reranker-DudpN0Ck.svg) | Reranker API | `https://api.jina.ai/v1/rerank` | Rank documents by query | _block_ | 100 RPM & 100,000 TPM | 500 RPM & 2,000,000 TPM | _trending\_up_ 5,000 RPM & 50,000,000 TPM | _ssid\_chart_ depends on the input size _help_ | Count the number of tokens in the input request. | POST |
| ![Image 115](blob:http://localhost/47430e9cbced04c539a17eb39573e3a9) | Classifier API | `https://api.jina.ai/v1/train` | Train a classifier using labeled examples | _block_ | 25 RPM & 25,000 TPM | 125 RPM & 500,000 TPM | 1,250 RPM & 12,000,000 TPM | _ssid\_chart_ depends on the input size | Tokens counted as: input_tokens × num_iters | POST |
| ![Image 116](blob:http://localhost/47430e9cbced04c539a17eb39573e3a9) | Classifier API (Few-shot) | `https://api.jina.ai/v1/classify` | Classify inputs using a trained few-shot classifier | _block_ | 25 RPM & 25,000 TPM | 125 RPM & 500,000 TPM | 1,250 RPM & 12,000,000 TPM | _ssid\_chart_ depends on the input size | Tokens counted as: input_tokens | POST |
| ![Image 117](blob:http://localhost/47430e9cbced04c539a17eb39573e3a9) | Classifier API (Zero-shot) | `https://api.jina.ai/v1/classify` | Classify inputs using zero-shot classification | _block_ | 25 RPM & 25,000 TPM | 125 RPM & 500,000 TPM | 1,250 RPM & 12,000,000 TPM | _ssid\_chart_ depends on the input size | Tokens counted as: input_tokens + label_tokens | POST |
| ![Image 118](blob:http://localhost/d9cb1deb4878909b05c9cd0f15af4aac) | Segmenter API | `https://api.jina.ai/v1/segment` | Tokenize and segment long text | 20 RPM | 200 RPM | 200 RPM | 1,000 RPM | 0.3s | Token is not counted as usage. | GET/POST |
| ![Image 119](blob:http://localhost/db267ccec0291b9762c00dd4567c6a5c) | DeepSearch | `https://deepsearch.jina.ai/v1/chat/completions` | Reason, search and iterate to find the best answer | _block_ | 50 RPM | 50 RPM | 500 RPM | 56.7s | Count the total number of tokens in the whole process. | POST |

### [Do I need a commercial license?](https://jina.ai/embeddings#cc-self-check)

CC BY-NC License Self-Check

* * *

_play\_arrow_

Are you using our official API or official images on Azure, AWS, or GCP?

_play\_arrow_

Yes

No restrictions. Simply sign up and pay through our website or cloud marketplace.

_play\_arrow_

No

_play\_arrow_

Are you a paid Elastic customer?

_play\_arrow_

Yes

Commercial use is likely already included in your Elastic license. Contact your Elastic Sales representative if unsure.

[Contact sales](https://jina.ai/contact-sales)

_play\_arrow_

No

We're currently unable to issue standalone commercial licensing agreements. Please contact Elastic Sales for more information.

[Contact sales](https://jina.ai/contact-sales)

API-related common questions

_code_

Can I use the same API key for reader, embedding, reranking, classifying and fine-tuning APIs?

_keyboard\_arrow\_down_

Yes, the same API key is valid for all search foundation products from Jina AI. This includes the reader, embedding, reranking, classifying and fine-tuning APIs, with tokens shared between the all services.

_code_

Can I monitor the token usage of my API key?

_keyboard\_arrow\_down_

Yes, token usage can be monitored in the 'API Key & Billing' tab by entering your API key, allowing you to view the recent usage history and remaining tokens. If you have logged in to the API dashboard, these details can also be viewed in the 'Manage API Key' tab.

_code_

What should I do if I forget my API key?

_keyboard\_arrow\_down_

If you have misplaced a topped-up key and wish to retrieve it, please contact support AT jina.ai with your registered email for assistance. It's recommended to log in to keep your API key securely stored and easily accessible.

[Contact](https://jina.ai/contact-sales)

_code_

Do API keys expire?

_keyboard\_arrow\_down_

No, our API keys do not have an expiration date. However, if you suspect your key has been compromised and wish to retire it, please contact our support team for assistance. You can also revoke your key in [the API Key Management dashboard](https://jina.ai/api-dashboard).

[Contact](https://jina.ai/contact-sales)

_code_

Can I transfer tokens between API keys?

_keyboard\_arrow\_down_

Yes, you can transfer tokens from a premium key to another. After logging into your account on [the API Key Management dashboard](https://jina.ai/api-dashboard), use the settings of the key you want to transfer out to move all remaining paid tokens.

_code_

Can I revoke my API key?

_keyboard\_arrow\_down_

Yes, you can revoke your API key if you believe it has been compromised. Revoking a key will immediately disable it for all users who have stored it, and all remaining balance and associated properties will be permanently unusable. If the key is a premium key, you have the option to transfer the remaining paid balance to another key before revocation. Notice that this action cannot be undone. To revoke a key, go to the key settings in [the API Key Management dashboard](https://jina.ai/api-dashboard).

_code_

Why is the first request for some models slow?

_keyboard\_arrow\_down_

This is because our serverless architecture offloads certain models during periods of low usage. The initial request activates or 'warms up' the model, which may take a few seconds. After this initial activation, subsequent requests process much more quickly.

_code_

Is my API data used to train your models?

_keyboard\_arrow\_down_

No. We never use your API requests, inputs, or outputs to train our embedding, reranker, or any other models. Your data remains yours. We are SOC 2 Type I and Type II compliant.

_code_

What are the rate limits for Jina APIs?

_keyboard\_arrow\_down_

Rate limits apply per API key:

**Free:** 100 RPM, 100K TPM, 2 concurrent requests

**Paid:** 500 RPM, 2M TPM, 50 concurrent requests

**Premium:** 5,000 RPM, 50M TPM, 500 concurrent requests

There is also an IP-based rate limit of 10,000 requests per 60 seconds. These limits apply across all Jina APIs (Embeddings, Reranker, Reader, etc.).

_code_

Are there batch size limits for the APIs?

_keyboard\_arrow\_down_

There is **no batch size limit** for either the Embeddings or Reranker APIs. You can send as many items or documents as needed per request. Both APIs batch inputs internally by token count for optimal GPU utilization.

Billing-related common questions

_attach\_money_

Is billing based on the number of sentences or requests?

_keyboard\_arrow\_down_

Our pricing model is based on the total number of tokens processed, allowing users the flexibility to allocate these tokens across any number of sentences, offering a cost-effective solution for diverse text analysis requirements.

_attach\_money_

Is there a free trial available for new users?

_keyboard\_arrow\_down_

We offer a welcoming free trial to new users, which includes ten millions tokens for use with any of our models, facilitated by an auto-generated API key. Once the free token limit is reached, users can easily purchase additional tokens for their API keys via the 'Buy tokens' tab.

_attach\_money_

Are tokens charged for failed requests?

_keyboard\_arrow\_down_

No, tokens are not deducted for failed requests.

_attach\_money_

What payment methods are accepted?

_keyboard\_arrow\_down_

Payments are processed through Stripe, supporting a variety of payment methods including credit cards, Google Pay, and PayPal for your convenience.

_attach\_money_

Is invoicing available for token purchases?

_keyboard\_arrow\_down_

Yes, an invoice will be issued to the email address associated with your Stripe account upon the purchase of tokens.

Offices

_location\_on_

Sunnyvale, CA

710 Lakeway Dr, Ste 200, Sunnyvale, CA 94085, USA

_location\_on_

Berlin, Germany

Prinzessinnenstraße 19-20, 10969 Berlin, Germany

Search Foundation

[Reader](https://jina.ai/reader)[Embeddings](https://jina.ai/embeddings)[Reranker](https://jina.ai/reranker)

Get Jina API key

[Rate Limit](https://jina.ai/contact-sales#rate-limit)[API Status](https://status.jina.ai/)

Company

[About us](https://jina.ai/about-us)[Contact sales](https://jina.ai/contact-sales)[News](https://jina.ai/news)[Intern program](https://jina.ai/internship)[Download Jina logo _open\_in\_new_](https://jina.ai/logo-Jina-1024.zip)[Download Elastic logo _open\_in\_new_](https://brand.elastic.co/302f66895/p/06c73c-elastic-logos/b/35d033)

Terms

[Security](https://jina.ai/legal#security-as-company-value)[Terms & Conditions](https://jina.ai/legal/#terms-and-conditions)[Privacy](https://jina.ai/legal/#privacy-policy)[Manage Cookies](javascript:UC_UI.showSecondLayer();)[![Image 120](https://jina.ai/21972-312_SOC_NonCPA_Blk.svg)](https://app.eu.vanta.com/jinaai/trust/vz7f4mohp0847aho84lmva)

[](https://x.com/jinaAI_)[](https://www.linkedin.com/company/jinaai/)[](https://github.com/jina-ai)[_![Image 121](https://jina.ai/huggingface\_logo.svg)_](https://huggingface.co/jinaai)[_email_](https://jina.ai/cdn-cgi/l/email-protection#3d4e484d4d524f497d5754535c135c54)

Jina AI by Elastic © 2020-2026.