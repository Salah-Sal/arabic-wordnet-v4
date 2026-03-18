> ## Documentation Index
> Fetch the complete documentation index at: https://docs.trychroma.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Jina AI

export const Callout = ({title, children}) => <div className="my-6">
    <div className="relative pr-1.5 pb-1.5">
      <div className="absolute top-1.5 left-1.5 right-0 bottom-0 bg-blue-500 dark:bg-blue-600" />
      <div className="relative border border-black dark:border-gray-500 px-5 py-4 bg-white dark:bg-neutral-900">
        {title && <p className="block mb-2"><strong>{title}</strong></p>}
        {children}
      </div>
    </div>
  </div>;

Chroma provides a convenient wrapper around JinaAI's embedding API. This embedding function runs remotely on JinaAI's servers, and requires an API key. You can get an API key by signing up for an account at [JinaAI](https://jina.ai/embeddings/).

<CodeGroup>
  ```python Python theme={null}
  from chromadb.utils.embedding_functions import JinaEmbeddingFunction
  jinaai_ef = JinaEmbeddingFunction(
      api_key="YOUR_API_KEY",
      model_name="jina-embeddings-v2-base-en",
  )
  jinaai_ef(input=["This is my first text to embed", "This is my second document"])
  ```

  ```typescript TypeScript theme={null}
  // npm install @chroma-core/jina

  import { JinaEmbeddingFunction } from '@chroma-core/jina';

  const embedder = new JinaEmbeddingFunction({
      jinaai_api_key: 'jina_****',
      model_name: 'jina-embeddings-v2-base-en',
  });

  // use directly
  const embeddings = embedder.generate(['document1', 'document2']);

  // pass documents to query for .add and .query
  const collection = await client.createCollection({name: "name", embeddingFunction: embedder})
  const collectionGet = await client.getCollection({name:"name", embeddingFunction: embedder})
  ```
</CodeGroup>

You can pass in an optional `model_name` argument, which lets you choose which Jina model to use. By default, Chroma uses `jina-embedding-v2-base-en`.

<Callout>
  Jina has added new attributes on embedding functions, including `task`, `late_chunking`, `truncate`, `dimensions`, `embedding_type`, and `normalized`. See [JinaAI](https://jina.ai/embeddings/) for references on which models support these attributes.
</Callout>

### Late Chunking Example

jina-embeddings-v3 supports [Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/), a technique to leverage the model's long-context capabilities for generating contextual chunk embeddings. Include `late_chunking=True` in your request to enable contextual chunked representation. When set to true, Jina AI API will concatenate all sentences in the input field and feed them as a single string to the model. Internally, the model embeds this long concatenated string and then performs late chunking, returning a list of embeddings that matches the size of the input list.

```python  theme={null}
from chromadb.utils.embedding_functions import JinaEmbeddingFunction
jinaai_ef = JinaEmbeddingFunction(
    api_key="YOUR_API_KEY",
    model_name="jina-embeddings-v3",
    late_chunking=True,
    task="text-matching",
)

collection = client.create_collection(name="late_chunking", embedding_function=jinaai_ef)

documents = [
    'Berlin is the capital and largest city of Germany.',
    'The city has a rich history dating back centuries.',
    'It was founded in the 13th century and has been a significant cultural and political center throughout European history.',
]

ids = [str(i+1) for i in range(len(documents))]

collection.add(ids=ids, documents=documents)

results = normal_collection.query(
    query_texts=["What is Berlin's population?", "When was Berlin founded?"],
    n_results=1,
)

print(results)
```

### Task parameter

`jina-embeddings-v3` has been trained with 5 task-specific adapters for different embedding uses. Include task in your request to optimize your downstream application:

* `retrieval.query`: Used to encode user queries or questions in retrieval tasks.
* `retrieval.passage`: Used to encode large documents in retrieval tasks at indexing time.
* `classification`: Used to encode text for text classification tasks.
* `text-matching`: Used to encode text for similarity matching, such as measuring similarity between two sentences.
* `separation`: Used for clustering or reranking tasks.


Built with [Mintlify](https://mintlify.com).