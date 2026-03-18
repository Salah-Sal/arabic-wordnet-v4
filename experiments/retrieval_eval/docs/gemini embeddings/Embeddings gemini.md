<br />

The Gemini API offers embedding models to generate embeddings for text, images,
video, and other content. These resulting embeddings can then be used for tasks
such as semantic search, classification, and clustering, providing more accurate,
context-aware results than keyword-based approaches.

The latest model, `gemini-embedding-2-preview`, is the first multimodal
embedding model in the Gemini API. It maps text, images,
video, audio, and documents into a unified embedding space, enabling cross-modal
search, classification, and clustering across over 100 languages. See the
[multimodal embeddings section](https://ai.google.dev/gemini-api/docs/embeddings#multimodal) to learn more. For text-only
use cases, `gemini-embedding-001` remains available.

Building Retrieval Augmented Generation (RAG) systems is a common use case for
AI products. Embeddings play a key role in significantly enhancing model outputs
with improved factual accuracy, coherence, and contextual richness. If you prefer
to use a managed RAG solution, we built the [File Search](https://ai.google.dev/gemini-api/docs/file-search)
tool which makes doing RAG easier to manage and more cost effective.

## Generating embeddings

Use the `embedContent` method to generate text embeddings:

### Python

    from google import genai

    client = genai.Client()

    result = client.models.embed_content(
            model="gemini-embedding-001",
            contents="What is the meaning of life?"
    )

    print(result.embeddings)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {

        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: 'What is the meaning of life?',
        });

        console.log(response.embeddings);
    }

    main();

### Go

    package main

    import (
        "context"
        "encoding/json"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
        }
        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }

        embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(string(embeddings))
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "model": "models/gemini-embedding-001",
            "content": {
            "parts": [{
                "text": "What is the meaning of life?"
            }]
            }
        }'

You can also generate embeddings for multiple chunks at once by passing them in
as a list of strings.

### Python

    from google import genai

    client = genai.Client()

    result = client.models.embed_content(
            model="gemini-embedding-001",
            contents= [
                "What is the meaning of life?",
                "What is the purpose of existence?",
                "How do I bake a cake?"
            ]
    )

    for embedding in result.embeddings:
        print(embedding)

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {

        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: [
                'What is the meaning of life?',
                'What is the purpose of existence?',
                'How do I bake a cake?'
            ],
        });

        console.log(response.embeddings);
    }

    main();

### Go

    package main

    import (
        "context"
        "encoding/json"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?"),
            genai.NewContentFromText("How does photosynthesis work?"),
            genai.NewContentFromText("Tell me about the history of the internet."),
        }
        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            nil,
        )
        if err != nil {
            log.Fatal(err)
        }

        embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(string(embeddings))
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -d '{
        "content": {
            "parts": [
            {
                "text": "What is the meaning of life?"
            },
            {
                "text": "How much wood would a woodchuck chuck?"
            },
            {
                "text": "How does the brain work?"
            }
            ]
        },
        "taskType": "SEMANTIC_SIMILARITY"
        }'

## Specify task type to improve performance

You can use embeddings for a wide range of tasks from classification to document
search. Specifying the right task type helps optimize the embeddings for the
intended relationships, maximizing accuracy and efficiency. For a complete list
of supported task types, see the [Supported task types](https://ai.google.dev/gemini-api/docs/embeddings#supported-task-types)
table.

The following example shows how you can use
`SEMANTIC_SIMILARITY` to check how similar in meaning strings of texts are.

> [!NOTE]
> **Note:** Cosine similarity is a good distance metric because it focuses on direction rather than magnitude, which more accurately reflects conceptual closeness. Values range from -1 (opposite) to 1 (greatest similarity).

### Python

    from google import genai
    from google.genai import types
    import pandas as pd
    from sklearn.metrics.pairwise import cosine_similarity

    client = genai.Client()

    texts = [
        "What is the meaning of life?",
        "What is the purpose of existence?",
        "How do I bake a cake?",
    ]

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts,
        config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY")
    )

    # Create a 3x3 table to show the similarity matrix
    df = pd.DataFrame(
        cosine_similarity([e.values for e in result.embeddings]),
        index=texts,
        columns=texts,
    )

    print(df)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as cosineSimilarity from "compute-cosine-similarity";

    async function main() {
        const ai = new GoogleGenAI({});

        const texts = [
            "What is the meaning of life?",
            "What is the purpose of existence?",
            "How do I bake a cake?",
        ];

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            contents: texts,
            taskType: 'SEMANTIC_SIMILARITY'
        });

        const embeddings = response.embeddings.map(e => e.values);

        for (let i = 0; i < texts.length; i++) {
            for (let j = i + 1; j < texts.length; j++) {
                const text1 = texts[i];
                const text2 = texts[j];
                const similarity = cosineSimilarity(embeddings[i], embeddings[j]);
                console.log(`Similarity between '${text1}' and '${text2}': ${similarity.toFixed(4)}`);
            }
        }
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"
        "math"

        "google.golang.org/genai"
    )

    // cosineSimilarity calculates the similarity between two vectors.
    func cosineSimilarity(a, b []float32) (float64, error) {
        if len(a) != len(b) {
            return 0, fmt.Errorf("vectors must have the same length")
        }

        var dotProduct, aMagnitude, bMagnitude float64
        for i := 0; i < len(a); i++ {
            dotProduct += float64(a[i] * b[i])
            aMagnitude += float64(a[i] * a[i])
            bMagnitude += float64(b[i] * b[i])
        }

        if aMagnitude == 0 || bMagnitude == 0 {
            return 0, nil
        }

        return dotProduct / (math.Sqrt(aMagnitude) * math.Sqrt(bMagnitude)), nil
    }

    func main() {
        ctx := context.Background()
        client, _ := genai.NewClient(ctx, nil)
        defer client.Close()

        texts := []string{
            "What is the meaning of life?",
            "What is the purpose of existence?",
            "How do I bake a cake?",
        }

        var contents []*genai.Content
        for _, text := range texts {
            contents = append(contents, genai.NewContentFromText(text, genai.RoleUser))
        }

        result, _ := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            &genai.EmbedContentRequest{TaskType: genai.TaskTypeSemanticSimilarity},
        )

        embeddings := result.Embeddings

        for i := 0; i < len(texts); i++ {
            for j := i + 1; j < len(texts); j++ {
                similarity, _ := cosineSimilarity(embeddings[i].Values, embeddings[j].Values)
                fmt.Printf("Similarity between '%s' and '%s': %.4f\n", texts[i], texts[j], similarity)
            }
        }
    }

### REST

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -d '{
        "taskType": "SEMANTIC_SIMILARITY",
        "content": {
            "parts": [
            {
                "text": "What is the meaning of life?"
            },
            {
                "text": "How much wood would a woodchuck chuck?"
            },
            {
                "text": "How does the brain work?"
            }
            ]
        }
        }'

The code snippets will show how similar the different chunks of text are to one
another when run.

### Supported task types

| Task type | Description | Examples |
|---|---|---|
| **SEMANTIC_SIMILARITY** | Embeddings optimized to assess text similarity. | Recommendation systems, duplicate detection |
| **CLASSIFICATION** | Embeddings optimized to classify texts according to preset labels. | Sentiment analysis, spam detection |
| **CLUSTERING** | Embeddings optimized to cluster texts based on their similarities. | Document organization, market research, anomaly detection |
| **RETRIEVAL_DOCUMENT** | Embeddings optimized for document search. | Indexing articles, books, or web pages for search. |
| **RETRIEVAL_QUERY** | Embeddings optimized for general search queries. Use `RETRIEVAL_QUERY` for queries; `RETRIEVAL_DOCUMENT` for documents to be retrieved. | Custom search |
| **CODE_RETRIEVAL_QUERY** | Embeddings optimized for retrieval of code blocks based on natural language queries. Use `CODE_RETRIEVAL_QUERY` for queries; `RETRIEVAL_DOCUMENT` for code blocks to be retrieved. | Code suggestions and search |
| **QUESTION_ANSWERING** | Embeddings for questions in a question-answering system, optimized for finding documents that answer the question. Use `QUESTION_ANSWERING` for questions; `RETRIEVAL_DOCUMENT` for documents to be retrieved. | Chatbox |
| **FACT_VERIFICATION** | Embeddings for statements that need to be verified, optimized for retrieving documents that contain evidence supporting or refuting the statement. Use `FACT_VERIFICATION` for the target text; `RETRIEVAL_DOCUMENT` for documents to be retrieved | Automated fact-checking systems |

## Controlling embedding size

Both `gemini-embedding-001` and `gemini-embedding-2-preview` are trained using
the Matryoshka Representation Learning (MRL) technique which teaches a model to
learn high-dimensional embeddings that have initial segments (or prefixes) which
are also useful, simpler versions of the same data.

Use the `output_dimensionality` parameter to control the size of
the output embedding vector. Selecting a smaller output dimensionality can save
storage space and increase computational efficiency for downstream applications,
while sacrificing little in terms of quality. By default, both models output a
3072-dimensional embedding, but you can truncate it to a smaller size without
losing quality to save storage space. We recommend using 768, 1536, or 3072
output dimensions.

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents="What is the meaning of life?",
        config=types.EmbedContentConfig(output_dimensionality=768)
    )

    [embedding_obj] = result.embeddings
    embedding_length = len(embedding_obj.values)

    print(f"Length of embedding: {embedding_length}")

### JavaScript

    import { GoogleGenAI } from "@google/genai";

    async function main() {
        const ai = new GoogleGenAI({});

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-001',
            content: 'What is the meaning of life?',
            outputDimensionality: 768,
        });

        const embeddingLength = response.embedding.values.length;
        console.log(`Length of embedding: ${embeddingLength}`);
    }

    main();

### Go

    package main

    import (
        "context"
        "fmt"
        "log"

        "google.golang.org/genai"
    )

    func main() {
        ctx := context.Background()
        // The client uses Application Default Credentials.
        // Authenticate with 'gcloud auth application-default login'.
        client, err := genai.NewClient(ctx, nil)
        if err != nil {
            log.Fatal(err)
        }
        defer client.Close()

        contents := []*genai.Content{
            genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
        }

        result, err := client.Models.EmbedContent(ctx,
            "gemini-embedding-001",
            contents,
            &genai.EmbedContentRequest{OutputDimensionality: 768},
        )
        if err != nil {
            log.Fatal(err)
        }

        embedding := result.Embeddings[0]
        embeddingLength := len(embedding.Values)
        fmt.Printf("Length of embedding: %d\n", embeddingLength)
    }

### REST

    curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
        -H 'Content-Type: application/json' \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -d '{
            "content": {"parts":[{ "text": "What is the meaning of life?"}]},
            "output_dimensionality": 768
        }'

Example output from the code snippet:

    Length of embedding: 768

## Ensuring quality for smaller dimensions

The 3072 dimension embedding is normalized. Normalized embeddings produce more
accurate semantic similarity by comparing vector direction, not magnitude. For
other dimensions, including 768 and 1536, you need to normalize the embeddings
as follows:

### Python

    import numpy as np
    from numpy.linalg import norm

    embedding_values_np = np.array(embedding_obj.values)
    normed_embedding = embedding_values_np / np.linalg.norm(embedding_values_np)

    print(f"Normed embedding length: {len(normed_embedding)}")
    print(f"Norm of normed embedding: {np.linalg.norm(normed_embedding):.6f}") # Should be very close to 1

Example output from this code snippet:

    Normed embedding length: 768
    Norm of normed embedding: 1.000000

The following table shows the MTEB scores, a commonly used benchmark for
embeddings, for different dimensions. Notably, the result shows that performance
is not strictly tied to the size of the embedding dimension, with lower
dimensions achieving scores comparable to their higher dimension counterparts.

| MRL Dimension | MTEB Score |
|---|---|
| 2048 | 68.16 |
| 1536 | 68.17 |
| 768 | 67.99 |
| 512 | 67.55 |
| 256 | 66.19 |
| 128 | 63.31 |

## Multimodal embeddings

The `gemini-embedding-2-preview` model supports multimodal input, allowing you
to embed images, video, audio, and documents content alongside text. All modalities
are mapped into the same embedding space, enabling cross-modal search and
comparison.

### Supported modalities and limits

The overall maximum input tokens limit is 8192 tokens.

| Modality | Specifications and limits |
|---|---|
| **Text** | Supports up to 8,192 tokens. |
| **Image** | Maximum of 6 images per request. Supported formats: PNG, JPEG. |
| **Audio** | Maximum duration of 80 seconds. Supported formats: MP3, WAV. |
| **Video** | Maximum duration of 128 seconds. Supported formats: MP4, MOV, Supported codec: H264, H265, AV1, VP9 |
| **Documents (PDF)** | Maximum of 6 pages. |

### Embedding images

The following example shows how to embed an image using
`gemini-embedding-2-preview`.

Images can be provided as inline data or as uploaded files
through the [Files API](https://ai.google.dev/gemini-api/docs/files).

### Python

    from google import genai
    from google.genai import types

    with open('example.png', 'rb') as f:
        image_bytes = f.read()

    client = genai.Client()

    result = client.models.embed_content(
        model='gemini-embedding-2-preview',
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type='image/png',
            ),
        ]
    )

    print(result.embeddings)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    async function main() {
        const ai = new GoogleGenAI({});

        const imgBase64 = fs.readFileSync("example.png", { encoding: "base64" });

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-2-preview',
            contents: [{
                inlineData: {
                    mimeType: 'image/png',
                    data: imgBase64,
                },
            }],
        });

        console.log(response.embeddings);
    }

    main();

### REST

    IMG_PATH="/path/to/your/image.png"
    IMG_BASE64=$(base64 -w0 "${IMG_PATH}")

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2-preview:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "content": {
                "parts": [{
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": "'"${IMG_BASE64}"'"
                    }
                }]
            }
        }'

### Embedding aggregation

When working with multimodal content, how you structure your input affects the
embedding output:

- **Single content entry:** Submitting multiple parts (for example, text and an image) within a single content entry produces one aggregated embedding for all modalities within that entry.
- **Multiple entries:** Sending multiple entries in the `contents` array returns separate embeddings for each entry.
- **Post-level representation:** For complex objects like social media posts with multiple media items, we recommend aggregating separate embeddings (for example, by averaging) to create a coherent post-level representation.

The following example shows how to create one aggregated embedding for text and image input.
Use the `parts` field to combine multiple inputs:

### Python

    from google import genai
    from google.genai import types

    with open('dog.png', 'rb') as f:
        image_bytes = f.read()

    result = client.models.embed_content(
        model='gemini-embedding-2-preview',
        contents=[
            types.Content(
                parts=[
                    types.Part(text="An image of a dog"),
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/png',
                    )
                ]
            )
        ]
    )

    # This produces one embedding
    for embedding in result.embeddings:
        print(embedding.values)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    async function main() {
        const ai = new GoogleGenAI({});

        const imgBase64 = fs.readFileSync("dog.png", { encoding: "base64" });

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-2-preview',
            contents: {
                parts: [
                    { text: 'An image of a dog' },
                    { inlineData: { mimeType: 'image/png', data: imgBase64 } },
                ],
            },
        });

        console.log(response.embeddings);
    }

    main();

### REST

    IMG_PATH="/path/to/your/dog.png"
    IMG_BASE64=$(base64 -w0 "${IMG_PATH}")

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2-preview:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "content": {
                "parts": [
                    {"text": "An image of a dog"},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": "'"${IMG_BASE64}"'"
                        }
                    }
                ]
            }
        }'

On the other hand, this example creates multiple embeddings in one embedding call:

### Python

    from google import genai
    from google.genai import types

    with open('dog.png', 'rb') as f:
        image_bytes = f.read()

    result = client.models.embed_content(
        model='gemini-embedding-2-preview',
        contents=[
            "The dog is cute",
            types.Part.from_bytes(
                data=image_bytes,
                mime_type='image/png',
            ),
        ]
    )

    # This produces two embeddings
    for embedding in result.embeddings:
        print(embedding.values)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    async function main() {
        const ai = new GoogleGenAI({});

        const imgBase64 = fs.readFileSync("dog.png", { encoding: "base64" });

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-2-preview',
            contents: [
                'The dog is cute',
                {
                    inlineData: {
                        mimeType: 'image/png',
                        data: imgBase64,
                    },
                },
            ],
        });

        console.log(response.embeddings);
    }

    main();

### REST

    IMG_PATH="/path/to/your/dog.png"
    IMG_BASE64=$(base64 -w0 "${IMG_PATH}")

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2-preview:batchEmbedContents" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "requests": [
                {
                    "model": "models/gemini-embedding-2-preview",
                    "content": {"parts": [{"text": "The dog is cute"}]}
                },
                {
                    "model": "models/gemini-embedding-2-preview",
                    "content": {"parts": [{"inline_data": {"mime_type": "image/png", "data": "'"${IMG_BASE64}"'"}}]}
                }
            ]
        }'

### Embedding audio

The following example shows how to embed an audio file using
`gemini-embedding-2-preview`.

Audio files can be provided as inline data or as uploaded files
through the [Files API](https://ai.google.dev/gemini-api/docs/files).

### Python

    from google import genai
    from google.genai import types

    with open('example.mp3', 'rb') as f:
        audio_bytes = f.read()

    client = genai.Client()

    result = client.models.embed_content(
        model='gemini-embedding-2-preview',
        contents=[
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type='audio/mpeg',
            ),
        ]
    )

    print(result.embeddings)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    async function main() {
        const ai = new GoogleGenAI({});

        const audioBase64 = fs.readFileSync("example.mp3", { encoding: "base64" });

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-2-preview',
            contents: [{
                inlineData: {
                    mimeType: 'audio/mpeg',
                    data: audioBase64,
                },
            }],
        });

        console.log(response.embeddings);
    }

    main();

### REST

    AUDIO_PATH="/path/to/your/example.mp3"
    AUDIO_BASE64=$(base64 -w0 "${AUDIO_PATH}")

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2-preview:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "content": {
                "parts": [{
                    "inline_data": {
                        "mime_type": "audio/mpeg",
                        "data": "'"${AUDIO_BASE64}"'"
                    }
                }]
            }
        }'

### Embedding video

The following example shows how to embed a video using
`gemini-embedding-2-preview`.

Videos can be provided as inline data or as uploaded files
through the [Files API](https://ai.google.dev/gemini-api/docs/files).

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()

    with open('example.mp4', 'rb') as f:
        video_bytes = f.read()

    result = client.models.embed_content(
        model='gemini-embedding-2-preview',
        contents=[
            types.Part.from_bytes(
                data=video_bytes,
                mime_type='video/mp4',
            ),
        ]
    )

    print(result.embeddings[0].values)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    async function main() {
        const ai = new GoogleGenAI({});

        const videoBase64 = fs.readFileSync("example.mp4", { encoding: "base64" });

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-2-preview',
            contents: [{
                inlineData: {
                    mimeType: 'video/mp4',
                    data: videoBase64,
                },
            }],
        });

        console.log(response.embeddings);
    }

    main();

### REST

    VIDEO_PATH="/path/to/your/video.mp4"
    VIDEO_BASE64=$(base64 -w0 "${VIDEO_PATH}")

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2-preview:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "content": {
                "parts": [{
                    "inline_data": {
                        "mime_type": "video/mp4",
                        "data": "'"${VIDEO_BASE64}"'"
                    }
                }]
            }
        }'

If you need to embed videos \>128 seconds, you can chunk the video into
overlapping segments and embed those chunks individually.

### Embedding documents

documents in PDF format can be embedded directly. The model processes the visual and text
content of each page.

PDFs can be provided as inline data or as uploaded files
through the [Files API](https://ai.google.dev/gemini-api/docs/files).

### Python

    from google import genai
    from google.genai import types

    with open('example.pdf', 'rb') as f:
        pdf_bytes = f.read()

    client = genai.Client()

    result = client.models.embed_content(
        model='gemini-embedding-2-preview',
        contents=[
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type='application/pdf',
            ),
        ]
    )

    print(result.embeddings)

### JavaScript

    import { GoogleGenAI } from "@google/genai";
    import * as fs from "node:fs";

    async function main() {
        const ai = new GoogleGenAI({});

        const pdfBase64 = fs.readFileSync("example.pdf", { encoding: "base64" });

        const response = await ai.models.embedContent({
            model: 'gemini-embedding-2-preview',
            contents: [{
                inlineData: {
                    mimeType: 'application/pdf',
                    data: pdfBase64,
                },
            }],
        });

        console.log(response.embeddings);
    }

    main();

### REST

    PDF_PATH="/path/to/your/example.pdf"
    PDF_BASE64=$(base64 -w0 "${PDF_PATH}")

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2-preview:embedContent" \
        -H "Content-Type: application/json" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -d '{
            "content": {
                "parts": [{
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": "'"${PDF_BASE64}"'"
                    }
                }]
            }
        }'

## Use cases

Text embeddings are crucial for a variety of common AI use cases, such as:

- **Retrieval-Augmented Generation (RAG):** Embeddings enhance the quality of generated text by retrieving and incorporating relevant information into the context of a model.
- **Information retrieval:** Search for the most semantically similar text or
  documents given a piece of input text.

  [Document search tutorial](https://github.com/google-gemini/cookbook/blob/main/examples/Talk_to_documents_with_embeddings.ipynb)
- **Search reranking**: Prioritize the most relevant items by semantically
  scoring initial results against the query.

  [Search reranking tutorial](https://github.com/google-gemini/cookbook/blob/main/examples/Search_reranking_using_embeddings.ipynb)
- **Anomaly detection:** Comparing groups of embeddings can help identify
  hidden trends or outliers.

  [Anomaly detection tutorial](https://github.com/google-gemini/cookbook/blob/main/examples/Anomaly_detection_with_embeddings.ipynb)
- **Classification:** Automatically categorize text based on its content, such
  as sentiment analysis or spam detection

  [Classification tutorial](https://github.com/google-gemini/cookbook/blob/main/examples/Classify_text_with_embeddings.ipynb)
- **Clustering:** Effectively grasp complex relationships by creating clusters
  and visualizations of your embeddings.

  [Clustering visualization tutorial](https://github.com/google-gemini/cookbook/blob/main/examples/clustering_with_embeddings.ipynb)

## Storing embeddings

As you take embeddings to production, it is common to
use **vector databases** to efficiently store, index, and retrieve
high-dimensional embeddings. Google Cloud offers managed data services that
can be used for this purpose including
[BigQuery](https://cloud.google.com/bigquery/docs/introduction),
[AlloyDB](https://cloud.google.com/alloydb/docs/overview), and
[Cloud SQL](https://cloud.google.com/sql/docs/postgres/introduction).

The following tutorials show how to use other third party vector databases
with Gemini Embedding.

- [ChromaDB tutorials](https://docs.trychroma.com/integrations/embedding-models/google-gemini)
- [QDrant tutorials](https://qdrant.tech/documentation/embeddings/gemini/)
- [Weaviate tutorials](https://docs.weaviate.io/weaviate/model-providers/google)
- [Pinecone tutorials](https://github.com/google-gemini/cookbook/blob/main/examples/langchain/Gemini_LangChain_QA_Pinecone_WebLoad.ipynb)

## Model versions

### Gemini Embedding 2 Preview

| Property | Description |
|---|---|
| Model code | **Gemini API** `gemini-embedding-2-preview` |
| Supported data types | **Input** Text, image, video, audio, PDF **Output** Text embeddings |
| Token limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 8,192 **Output dimension size** Flexible, supports: 128 - 3072, Recommended: 768, 1536, 3072 |
| Versions | Read the [model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions) for more details. - Preview: `gemini-embedding-2-preview` |
| Latest update | November 2025 |

### Gemini Embedding

| Property | Description |
|---|---|
| Model code | **Gemini API** `gemini-embedding-001` |
| Supported data types | **Input** Text **Output** Text embeddings |
| Token limits^[\[\*\]](https://ai.google.dev/gemini-api/docs/tokens)^ | **Input token limit** 2,048 **Output dimension size** Flexible, supports: 128 - 3072, Recommended: 768, 1536, 3072 |
| Versions | Read the [model version patterns](https://ai.google.dev/gemini-api/docs/models/gemini#model-versions) for more details. - Stable: `gemini-embedding-001` |
| Latest update | June 2025 |

For deprecated Embeddings models, visit the [Deprecations](https://ai.google.dev/gemini-api/docs/deprecations) page

## Migration from gemini-embedding-001

The embedding spaces between `gemini-embedding-001` and
`gemini-embedding-2-preview` are **incompatible** . This means you cannot
directly compare embeddings generated by one model with embeddings generated by
the other. If you are upgrading to `gemini-embedding-2-preview`, you must
re-embed all of your existing data.

## Batch embeddings

If latency is not a concern, try using the Gemini Embeddings models with
[Batch API](https://ai.google.dev/gemini-api/docs/batch-api#batch-embedding). This
allows for much higher throughput at 50% of the default Embedding price.
Find examples on how to get started in the [Batch API cookbook](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Batch_mode.ipynb).

## Responsible use notice

Unlike generative AI models that create new content, the Gemini Embedding model
is only intended to transform the format of your input data into a numerical
representation. While Google is responsible for providing an embedding model
that transforms the format of your input data to the numerical-format requested,
users retain full responsibility for the data they input and the resulting
embeddings. By using the Gemini Embedding model you confirm that you have the
necessary rights to any content that you upload. Do not generate content that
infringes on others' intellectual property or privacy rights. Your use of this
service is subject to our [Prohibited Use
Policy](https://policies.google.com/terms/generative-ai/use-policy) and
[Google's Terms of Service](https://ai.google.dev/gemini-api/terms).

## Start building with embeddings

Check out the [embeddings quickstart
notebook](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Embeddings.ipynb)
to explore the model capabilities and learn how to customize and visualize your
embeddings.