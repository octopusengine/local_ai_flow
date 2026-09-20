> ## Documentation Index

> Fetch the complete documentation index at: https://docs.typesafe.ai/llms.txt

> Use this file to discover all available pages before exploring further.



\# JavaScript SDK



JavaScript and TypeScript SDK for \[TypeSafe AI](https://typesafe.ai).



\## Quickstart



Install the SDK (Node.js 20 or newer):



```sh theme={null}

npm install @typesafe-ai/sdk

```



Set `TYPESAFE\_API\_KEY` in your environment, then create and use the client:



```ts theme={null}

import { choice, TypeSafeClient } from "@typesafe-ai/sdk";



const client = new TypeSafeClient();

const response = await client.systemOne({

&#x20; state: { document: "I was charged twice. Please fix this ASAP." },

&#x20; questions: {

&#x20;   category: choice("What is this ticket about?", {

&#x20;     billing: null,

&#x20;     technical: null,

&#x20;     other: null,

&#x20;   }),

&#x20; },

});



console.log(response.answers.category.choice);

```



Answer types are inferred from your questions. The package includes ESM, CommonJS, and TypeScript declarations.



\## Documentation



Learn what TypeSafe can do in the \[TypeSafe docs](https://docs.typesafe.ai/).

See the SDK's \[client](https://github.com/typesafe-ai/typesafe-sdk-js/blob/v0.6.0/src/client.ts) and \[types](https://github.com/typesafe-ai/typesafe-sdk-js/blob/v0.6.0/src/types.ts) for API options and defaults.

