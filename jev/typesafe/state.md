> ## Documentation Index

> Fetch the complete documentation index at: https://docs.typesafe.ai/llms.txt

> Use this file to discover all available pages before exploring further.



\# State



> What state is, how to structure it, and how to give a System One model the context it needs.



\*\*State\*\* is the content you ask a System One model to evaluate. It could be a support message, a passage of text, or the current state of your application. You pass it in the `state` field of an API request, alongside the questions you want answered.



Each request evaluates one state against one or more questions. All questions see the same state and are evaluated independently. You can mix \[Choice](/primitives/choice), \[Score](/primitives/score), and \[Noul](/primitives/noul) questions in one request.



\## State can be a simple string or a structured JSON value



The simplest state is a plain string:



```python theme={null}

state = "My card was charged twice."

```



State can also be a JSON object or array containing related context, examples, and other information that helps the model answer the associated questions. Think of state as the material you would present to a panel of experts before asking them to make a judgment. In Python, pass the corresponding string, dictionary, or list directly to `client.system\_one(state=...)`.



| Format | Useful for                                          | Example                                                                 |

| ------ | --------------------------------------------------- | ----------------------------------------------------------------------- |

| String | A message, article, or passage                      | `"My card was charged twice."`                                          |

| Object | Named fields, related records, or application state | `{"message": "My card was charged twice.", "order\_id": "A-104"}`        |

| Array  | A sequence of messages or records                   | `\["Hi", "My customer number is TS1337.", "My card was charged twice."]` |



Use an object for most requests so each part of the state has a descriptive name and its relationships remain clear. A string is suitable when the use case is simple and requires only one piece of text.



<Note>

&#x20; Jev accepts text only. State must be a string, JSON object, or array of text values. Images, audio, and video are not supported (yet). Jev's primary training language is English; other languages, including CJK scripts, are accepted but currently have lower accuracy — see \[Models](/models#language-support).

</Note>



```json title="A support conversation as state" theme={null}

{

&#x20; "ticket": {

&#x20;   "subject": "Duplicate charge",

&#x20;   "messages": \[

&#x20;     {"from": "customer", "text": "I was charged twice for order A-104. Please refund the duplicate."},

&#x20;     {"from": "support", "text": "We are checking the charges."}

&#x20;   ]

&#x20; },

&#x20; "order": {

&#x20;   "id": "A-104",

&#x20;   "charges": \[

&#x20;     {"amount\_usd": 49, "status": "captured"},

&#x20;     {"amount\_usd": 49, "status": "captured"}

&#x20;   ]

&#x20; },

&#x20; "refund\_policy": "Duplicate charges are eligible for a refund."

}

```



This object is one state, even though it contains a conversation, an order, and a policy. Put related information together when the decision requires comparing those parts.



\## Separate content from questions



The state contains the content and supporting facts. \[Questions](/primitives) define the judgments the model should make about that material. For example, keep the refund request and policy in the state, then ask whether the customer requested a refund and whether the policy supports it.



See \[Primitives (Questions)](/primitives) for guidance on instructions, criteria, question types, and asking several questions about one state.



See the \[API reference](/api) for the request schema and \[client SDKs](/sdk) for installation, typed inputs, and response handling.

