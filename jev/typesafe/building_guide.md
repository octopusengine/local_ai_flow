> ## Documentation Index

> Fetch the complete documentation index at: https://docs.typesafe.ai/llms.txt

> Use this file to discover all available pages before exploring further.



\# How to build with TypeSafe



> Design AI-powered software by keeping code in control and giving System One narrow, structured decisions.



export function TypesafeExample({example, display, title}) {

&#x20; const keyStrUriSafe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$";

&#x20; function compressToEncodedURIComponent(input) {

&#x20;   if (input == null) return "";

&#x20;   return \_compress(input, 6, function (a) {

&#x20;     return keyStrUriSafe.charAt(a);

&#x20;   });

&#x20; }

&#x20; function \_compress(uncompressed, bitsPerChar, getCharFromInt) {

&#x20;   if (uncompressed == null) return "";

&#x20;   var i, value, context\_dictionary = {}, context\_dictionaryToCreate = {}, context\_c = "", context\_wc = "", context\_w = "", context\_enlargeIn = 2, context\_dictSize = 3, context\_numBits = 2, context\_data = \[], context\_data\_val = 0, context\_data\_position = 0, ii;

&#x20;   for (ii = 0; ii < uncompressed.length; ii += 1) {

&#x20;     context\_c = uncompressed.charAt(ii);

&#x20;     if (!Object.prototype.hasOwnProperty.call(context\_dictionary, context\_c)) {

&#x20;       context\_dictionary\[context\_c] = context\_dictSize++;

&#x20;       context\_dictionaryToCreate\[context\_c] = true;

&#x20;     }

&#x20;     context\_wc = context\_w + context\_c;

&#x20;     if (Object.prototype.hasOwnProperty.call(context\_dictionary, context\_wc)) {

&#x20;       context\_w = context\_wc;

&#x20;     } else {

&#x20;       if (Object.prototype.hasOwnProperty.call(context\_dictionaryToCreate, context\_w)) {

&#x20;         if (context\_w.charCodeAt(0) < 256) {

&#x20;           for (i = 0; i < context\_numBits; i++) {

&#x20;             context\_data\_val = context\_data\_val << 1;

&#x20;             if (context\_data\_position == bitsPerChar - 1) {

&#x20;               context\_data\_position = 0;

&#x20;               context\_data.push(getCharFromInt(context\_data\_val));

&#x20;               context\_data\_val = 0;

&#x20;             } else {

&#x20;               context\_data\_position++;

&#x20;             }

&#x20;           }

&#x20;           value = context\_w.charCodeAt(0);

&#x20;           for (i = 0; i < 8; i++) {

&#x20;             context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;             if (context\_data\_position == bitsPerChar - 1) {

&#x20;               context\_data\_position = 0;

&#x20;               context\_data.push(getCharFromInt(context\_data\_val));

&#x20;               context\_data\_val = 0;

&#x20;             } else {

&#x20;               context\_data\_position++;

&#x20;             }

&#x20;             value = value >> 1;

&#x20;           }

&#x20;         } else {

&#x20;           value = 1;

&#x20;           for (i = 0; i < context\_numBits; i++) {

&#x20;             context\_data\_val = context\_data\_val << 1 | value;

&#x20;             if (context\_data\_position == bitsPerChar - 1) {

&#x20;               context\_data\_position = 0;

&#x20;               context\_data.push(getCharFromInt(context\_data\_val));

&#x20;               context\_data\_val = 0;

&#x20;             } else {

&#x20;               context\_data\_position++;

&#x20;             }

&#x20;             value = 0;

&#x20;           }

&#x20;           value = context\_w.charCodeAt(0);

&#x20;           for (i = 0; i < 16; i++) {

&#x20;             context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;             if (context\_data\_position == bitsPerChar - 1) {

&#x20;               context\_data\_position = 0;

&#x20;               context\_data.push(getCharFromInt(context\_data\_val));

&#x20;               context\_data\_val = 0;

&#x20;             } else {

&#x20;               context\_data\_position++;

&#x20;             }

&#x20;             value = value >> 1;

&#x20;           }

&#x20;         }

&#x20;         context\_enlargeIn--;

&#x20;         if (context\_enlargeIn == 0) {

&#x20;           context\_enlargeIn = Math.pow(2, context\_numBits);

&#x20;           context\_numBits++;

&#x20;         }

&#x20;         delete context\_dictionaryToCreate\[context\_w];

&#x20;       } else {

&#x20;         value = context\_dictionary\[context\_w];

&#x20;         for (i = 0; i < context\_numBits; i++) {

&#x20;           context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;           if (context\_data\_position == bitsPerChar - 1) {

&#x20;             context\_data\_position = 0;

&#x20;             context\_data.push(getCharFromInt(context\_data\_val));

&#x20;             context\_data\_val = 0;

&#x20;           } else {

&#x20;             context\_data\_position++;

&#x20;           }

&#x20;           value = value >> 1;

&#x20;         }

&#x20;       }

&#x20;       context\_enlargeIn--;

&#x20;       if (context\_enlargeIn == 0) {

&#x20;         context\_enlargeIn = Math.pow(2, context\_numBits);

&#x20;         context\_numBits++;

&#x20;       }

&#x20;       context\_dictionary\[context\_wc] = context\_dictSize++;

&#x20;       context\_w = String(context\_c);

&#x20;     }

&#x20;   }

&#x20;   if (context\_w !== "") {

&#x20;     if (Object.prototype.hasOwnProperty.call(context\_dictionaryToCreate, context\_w)) {

&#x20;       if (context\_w.charCodeAt(0) < 256) {

&#x20;         for (i = 0; i < context\_numBits; i++) {

&#x20;           context\_data\_val = context\_data\_val << 1;

&#x20;           if (context\_data\_position == bitsPerChar - 1) {

&#x20;             context\_data\_position = 0;

&#x20;             context\_data.push(getCharFromInt(context\_data\_val));

&#x20;             context\_data\_val = 0;

&#x20;           } else {

&#x20;             context\_data\_position++;

&#x20;           }

&#x20;         }

&#x20;         value = context\_w.charCodeAt(0);

&#x20;         for (i = 0; i < 8; i++) {

&#x20;           context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;           if (context\_data\_position == bitsPerChar - 1) {

&#x20;             context\_data\_position = 0;

&#x20;             context\_data.push(getCharFromInt(context\_data\_val));

&#x20;             context\_data\_val = 0;

&#x20;           } else {

&#x20;             context\_data\_position++;

&#x20;           }

&#x20;           value = value >> 1;

&#x20;         }

&#x20;       } else {

&#x20;         value = 1;

&#x20;         for (i = 0; i < context\_numBits; i++) {

&#x20;           context\_data\_val = context\_data\_val << 1 | value;

&#x20;           if (context\_data\_position == bitsPerChar - 1) {

&#x20;             context\_data\_position = 0;

&#x20;             context\_data.push(getCharFromInt(context\_data\_val));

&#x20;             context\_data\_val = 0;

&#x20;           } else {

&#x20;             context\_data\_position++;

&#x20;           }

&#x20;           value = 0;

&#x20;         }

&#x20;         value = context\_w.charCodeAt(0);

&#x20;         for (i = 0; i < 16; i++) {

&#x20;           context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;           if (context\_data\_position == bitsPerChar - 1) {

&#x20;             context\_data\_position = 0;

&#x20;             context\_data.push(getCharFromInt(context\_data\_val));

&#x20;             context\_data\_val = 0;

&#x20;           } else {

&#x20;             context\_data\_position++;

&#x20;           }

&#x20;           value = value >> 1;

&#x20;         }

&#x20;       }

&#x20;       context\_enlargeIn--;

&#x20;       if (context\_enlargeIn == 0) {

&#x20;         context\_enlargeIn = Math.pow(2, context\_numBits);

&#x20;         context\_numBits++;

&#x20;       }

&#x20;       delete context\_dictionaryToCreate\[context\_w];

&#x20;     } else {

&#x20;       value = context\_dictionary\[context\_w];

&#x20;       for (i = 0; i < context\_numBits; i++) {

&#x20;         context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;         if (context\_data\_position == bitsPerChar - 1) {

&#x20;           context\_data\_position = 0;

&#x20;           context\_data.push(getCharFromInt(context\_data\_val));

&#x20;           context\_data\_val = 0;

&#x20;         } else {

&#x20;           context\_data\_position++;

&#x20;         }

&#x20;         value = value >> 1;

&#x20;       }

&#x20;     }

&#x20;     context\_enlargeIn--;

&#x20;     if (context\_enlargeIn == 0) {

&#x20;       context\_enlargeIn = Math.pow(2, context\_numBits);

&#x20;       context\_numBits++;

&#x20;     }

&#x20;   }

&#x20;   value = 2;

&#x20;   for (i = 0; i < context\_numBits; i++) {

&#x20;     context\_data\_val = context\_data\_val << 1 | value \& 1;

&#x20;     if (context\_data\_position == bitsPerChar - 1) {

&#x20;       context\_data\_position = 0;

&#x20;       context\_data.push(getCharFromInt(context\_data\_val));

&#x20;       context\_data\_val = 0;

&#x20;     } else {

&#x20;       context\_data\_position++;

&#x20;     }

&#x20;     value = value >> 1;

&#x20;   }

&#x20;   while (true) {

&#x20;     context\_data\_val = context\_data\_val << 1;

&#x20;     if (context\_data\_position == bitsPerChar - 1) {

&#x20;       context\_data.push(getCharFromInt(context\_data\_val));

&#x20;       break;

&#x20;     } else context\_data\_position++;

&#x20;   }

&#x20;   return context\_data.join("");

&#x20; }

&#x20; function buildHref(ex) {

&#x20;   const documentText = ex.state === undefined ? "" : typeof ex.state === "string" ? ex.state : JSON.stringify(ex.state, null, 2);

&#x20;   return "https://console.typesafe.ai/decode#share/" + compressToEncodedURIComponent(JSON.stringify({

&#x20;     apiVersion: "v1",

&#x20;     documentText,

&#x20;     promptsText: JSON.stringify(ex.questions, null, 2),

&#x20;     selectedModels: ex.selectedModels

&#x20;   }));

&#x20; }

&#x20; const displayedExample = display === "questions" ? example.questions : example.state === undefined ? {

&#x20;   questions: example.questions

&#x20; } : {

&#x20;   state: example.state,

&#x20;   questions: example.questions

&#x20; };

&#x20; const code = JSON.stringify(displayedExample, null, 2);

&#x20; const href = buildHref(example);

&#x20; return <div style={{

&#x20;   margin: "1.25rem 0"

&#x20; }}>

&#x20;     <CodeBlock language="json" filename={title ?? "request"}>

&#x20;       {code}

&#x20;     </CodeBlock>

&#x20;     <div className="pb-8">

&#x20;       <a href={href} target="\_blank" rel="noreferrer" className="text-primary">

&#x20;         Try it in the Playground →

&#x20;       </a>

&#x20;     </div>

&#x20;   </div>;

}



System One is TypeSafe's model for building AI-powered software, not agents. It does not generate code or choose its own next action. It provides AI primitives that embed into software, so code remains in control while the model handles common-sense judgments over unstructured data.



<Info>

&#x20; \*\*Summary:\*\* build a normal software workflow and insert System One only where AI is needed.



&#x20; \* Keep control flow, deterministic rules, and side effects in code.

&#x20; \* Break broad judgments into narrow, typed questions with explicit instructions and criteria.

&#x20; \* Give each question only the context it needs.

&#x20; \* Use probabilities and confidence to act, ask for review, or escalate.

&#x20; \* Ask independent questions together, then compose their answers in code.

</Info>



\## Three software architectures



TypeSafe is designed for building \*\*AI-powered software\*\*, where code owns the workflow and AI handles narrow, structured decisions.



<Tabs>

&#x20; <Tab title="Traditional software">

&#x20;   Traditional code is a complex decision tree made from simple software primitives. Because each primitive is reliable, developers can compose them into higher-level abstractions.

&#x20; </Tab>



&#x20; <Tab title="LLM agents">

&#x20;   An agent processes instructions and chooses its next step. This works well when a person is monitoring the process, but every loop introduces another opportunity to go off the rails.

&#x20; </Tab>



&#x20; <Tab title="AI-powered software">

&#x20;   Code handles deterministic work and owns the control flow. The model appears only where the system needs programmable common sense or needs to interpret unstructured data. Each AI task is kept atomic and constrained.

&#x20; </Tab>

</Tabs>



<Frame>

&#x20; <img className="block dark:hidden" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/how-to-build-with-typesafe/software-architectures-light.webp?fit=max\&auto=format\&n=aFVnpmCIX68NpsV1\&q=85\&s=35c7622176190d1b1f19dc712f2fbf11" alt="Traditional software, agents, and AI-powered software shown as three different system architectures." width="2048" height="1117" data-path="images/how-to-build-with-typesafe/software-architectures-light.webp" />



&#x20; <img className="hidden dark:block" src="https://mintcdn.com/ts-docs/aFVnpmCIX68NpsV1/images/how-to-build-with-typesafe/software-architectures-dark.webp?fit=max\&auto=format\&n=aFVnpmCIX68NpsV1\&q=85\&s=8e6c2c73bdd4c9b541c4f9294bd829b5" alt="Traditional software, agents, and AI-powered software shown as three different system architectures." width="2048" height="1117" data-path="images/how-to-build-with-typesafe/software-architectures-dark.webp" />

</Frame>



\## What makes System One composable



<Columns cols={2}>

&#x20; <Card title="Structured" icon="braces">

&#x20;   System One is type-safe by construction. Decisions and probabilities conform to the structured software types and JSON schema your code expects, so it never has to recover a value from generated prose.

&#x20; </Card>



&#x20; <Card title="Parallel" icon="split">

&#x20;   Questions are evaluated independently and in parallel. One primitive's result does not become hidden context that changes another primitive's result.

&#x20; </Card>



&#x20; <Card title="Comparable" icon="arrow-up-down">

&#x20;   Outputs are sortable and can drive smart `if` statements, thresholds, and comparisons.

&#x20; </Card>



&#x20; <Card title="Fast" icon="gauge">

&#x20;   Most queries complete in about 100 ms. System One is fast enough for real-time request paths and user interfaces.

&#x20; </Card>



&#x20; <Card title="Calibrated confidence" icon="chart-no-axes-combined">

&#x20;   \[RLCD](/introduction/machine-learning-primer) communicates uncertainty through calibrated probabilities instead of tending toward overconfidence.

&#x20; </Card>



&#x20; <Card title="Self-consistent" icon="repeat-2">

&#x20;   System One is designed to return stable answers across repeated evaluations. See the \[self-consistency cookbook](/cookbooks/consistency\_noul\_cookbook).

&#x20; </Card>

</Columns>



Because every output is constrained to the supplied options, the model returns a full probability distribution over those options rather than inventing a value outside the schema. TypeSafe's target is a greater than 100× intelligence-to-speed-and-cost ratio; the underlying bet is that cheaper intelligence will create much more demand.



\## Design a System One workflow



<Steps titleSize="h3">

&#x20; <Step title="Use code when you can">

&#x20;   Keep deterministic work in code. It is reliable and cheap. Avoid agent `while` loops when a software workflow can express the same behavior.



&#x20;   <Accordion title="Example: keep deterministic rules in code">

&#x20;     ```python theme={null}

&#x20;     days\_overdue = (today - invoice.due\_date).days



&#x20;     if days\_overdue > 30:

&#x20;         route\_to\_collections(invoice)

&#x20;     ```

&#x20;   </Accordion>



&#x20;   Browse the \[System One patterns](/patterns) for bounded ways to compose model decisions with code.

&#x20; </Step>



&#x20; <Step title="Decompose the input state">

&#x20;   Include only the context relevant to the current questions. This helps the model avoid distractions and context rot. Do not rely on knowledge stored in model weights when current information can come from your own knowledge base.



&#x20;   <Accordion title="Example: send only relevant context">

&#x20;     <TypesafeExample

&#x20;       title="request"

&#x20;       display="request"

&#x20;       example={{

&#x20;     state: {

&#x20;       ticket\_message: 'My flight was cancelled. Can I get a refund?',

&#x20;       refund\_policy: 'Cancelled flights are eligible for a full refund.',

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       policy\_supports\_refund: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does the refund policy support the refund requested in the ticket?',

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />

&#x20;   </Accordion>

&#x20; </Step>



&#x20; <Step title="Use structure in the input state">

&#x20;   Use nested JSON for the `state` and `questions` fields. Point questions at specific values when that removes ambiguity, and include the backtick characters around each path inside the question.



&#x20;   <Accordion title="Example: reference a nested value">

&#x20;     Use a backticked dot-and-index path to point a question at a specific nested value, such as `support.tickets\[0].message`.



&#x20;     <TypesafeExample

&#x20;       title="request"

&#x20;       display="request"

&#x20;       example={{

&#x20;     state: {

&#x20;       support: {

&#x20;         tickets: \[

&#x20;           { message: 'I was charged twice for order A-104.' },

&#x20;           { message: 'How do I reset my password?' },

&#x20;         ],

&#x20;       },

&#x20;       commerce: {

&#x20;         orders: \[

&#x20;           {

&#x20;             id: 'A-104',

&#x20;             charges: \[

&#x20;               { amount\_usd: 49, status: 'captured' },

&#x20;               { amount\_usd: 49, status: 'captured' },

&#x20;             ],

&#x20;           },

&#x20;         ],

&#x20;       },

&#x20;       account: {

&#x20;         security: {

&#x20;           password\_reset:

&#x20;             'Email a reset link to the address on file.',

&#x20;         },

&#x20;       },

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       duplicate\_charge: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Do `support.tickets\[0].message` and `commerce.orders\[0].charges` indicate a duplicate charge?',

&#x20;       },

&#x20;       password\_reset\_supported: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Can `account.security.password\_reset` resolve the request in `support.tickets\[1].message`?',

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />

&#x20;   </Accordion>

&#x20; </Step>



&#x20; <Step title="Decompose the questions">

&#x20;   Ask the most explicit, narrow, specific, atomic questions you can. Break down complex or ill-defined questions into separate questions that each evaluate one property.



&#x20;   <Info>

&#x20;     This is probably the most important concept in this guide. Broad questions hide several judgments behind one answer. Atomic questions expose those judgments so you can inspect, tune, and combine them in code.

&#x20;   </Info>



&#x20;   <Accordion title="Example: decompose spam detection">

&#x20;     <TypesafeExample

&#x20;       title="One broad question (bad)"

&#x20;       display="questions"

&#x20;       example={{

&#x20;     state: {

&#x20;       message: {

&#x20;         sender: {

&#x20;           display\_name: 'Acme Payroll',

&#x20;           email: 'rewards@claim-bonus.example',

&#x20;         },

&#x20;         subject: 'Urgent: claim your employee bonus',

&#x20;         body:

&#x20;           'You have been selected for a $1,000 bonus. Confirm your payroll password today to receive it.',

&#x20;         links: \[

&#x20;           {

&#x20;             text: 'Claim bonus',

&#x20;             url: 'http://claim-bonus.example/acme',

&#x20;           },

&#x20;         ],

&#x20;       },

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       is\_spam: {

&#x20;         type: 'noul',

&#x20;         instructions: 'Is `message` spam?',

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />



&#x20;     <TypesafeExample

&#x20;       title="Decomposed questions (good)"

&#x20;       display="questions"

&#x20;       example={{

&#x20;     state: {

&#x20;       message: {

&#x20;         sender: {

&#x20;           display\_name: 'Acme Payroll',

&#x20;           email: 'rewards@claim-bonus.example',

&#x20;         },

&#x20;         subject: 'Urgent: claim your employee bonus',

&#x20;         body:

&#x20;           'You have been selected for a $1,000 bonus. Confirm your payroll password today to receive it.',

&#x20;         links: \[

&#x20;           {

&#x20;             text: 'Claim bonus',

&#x20;             url: 'http://claim-bonus.example/acme',

&#x20;           },

&#x20;         ],

&#x20;       },

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       requests\_credentials: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `message.body` ask the recipient to provide a password or other login credential?',

&#x20;       },

&#x20;       offers\_unexpected\_reward: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `message.body` claim the recipient received an unexpected prize, payment, or reward?',

&#x20;       },

&#x20;       creates\_time\_pressure: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `message.subject` or `message.body` pressure the recipient to act quickly?',

&#x20;       },

&#x20;       sender\_identity\_mismatch: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does the organization named in `message.sender.display\_name` conflict with the domain in `message.sender.email`?',

&#x20;       },

&#x20;       link\_domain\_mismatch: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does the domain in `message.links\[0].url` conflict with the organization named in `message.sender.display\_name`?',

&#x20;       },

&#x20;       disguises\_link\_destination: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `message.links\[0].text` conceal or misrepresent the destination in `message.links\[0].url`?',

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />

&#x20;   </Accordion>



&#x20;   <Accordion title="Example: verify a tool-call trace">

&#x20;     <TypesafeExample

&#x20;       title="One broad question (bad)"

&#x20;       display="questions"

&#x20;       example={{

&#x20;     state: {

&#x20;       request: {

&#x20;         text: "What's the weather in Seattle tomorrow in Fahrenheit?",

&#x20;         location: 'Seattle, WA',

&#x20;         date: '2026-09-03',

&#x20;         unit: 'fahrenheit',

&#x20;       },

&#x20;       available\_tools: {

&#x20;         geocode\_city: {

&#x20;           description: 'Resolve a city to latitude and longitude.',

&#x20;           parameters: { city: 'string' },

&#x20;         },

&#x20;         get\_weather: {

&#x20;           description: 'Get the forecast for coordinates and a date.',

&#x20;           parameters: {

&#x20;             latitude: 'number',

&#x20;             longitude: 'number',

&#x20;             date: 'YYYY-MM-DD',

&#x20;             unit: \['fahrenheit', 'celsius'],

&#x20;           },

&#x20;         },

&#x20;       },

&#x20;       trace: {

&#x20;         tool\_calls: \[

&#x20;           {

&#x20;             id: 'call\_1',

&#x20;             name: 'geocode\_city',

&#x20;             arguments: { city: 'Seattle, WA' },

&#x20;           },

&#x20;           {

&#x20;             id: 'call\_2',

&#x20;             name: 'get\_weather',

&#x20;             arguments: {

&#x20;               latitude: 47.6062,

&#x20;               longitude: -122.3321,

&#x20;               date: '2026-09-03',

&#x20;               unit: 'celsius',

&#x20;             },

&#x20;           },

&#x20;         ],

&#x20;         tool\_results: \[

&#x20;           {

&#x20;             tool\_call\_id: 'call\_1',

&#x20;             output: { latitude: 47.6062, longitude: -122.3321 },

&#x20;           },

&#x20;         ],

&#x20;       },

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       tool\_calls\_are\_correct: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Is `trace.tool\_calls` correct for `request` and `available\_tools`?',

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />



&#x20;     <TypesafeExample

&#x20;       title="Decomposed questions (good)"

&#x20;       display="questions"

&#x20;       example={{

&#x20;     state: {

&#x20;       request: {

&#x20;         text: "What's the weather in Seattle tomorrow in Fahrenheit?",

&#x20;         location: 'Seattle, WA',

&#x20;         date: '2026-09-03',

&#x20;         unit: 'fahrenheit',

&#x20;       },

&#x20;       available\_tools: {

&#x20;         geocode\_city: {

&#x20;           description: 'Resolve a city to latitude and longitude.',

&#x20;           parameters: { city: 'string' },

&#x20;         },

&#x20;         get\_weather: {

&#x20;           description: 'Get the forecast for coordinates and a date.',

&#x20;           parameters: {

&#x20;             latitude: 'number',

&#x20;             longitude: 'number',

&#x20;             date: 'YYYY-MM-DD',

&#x20;             unit: \['fahrenheit', 'celsius'],

&#x20;           },

&#x20;         },

&#x20;       },

&#x20;       trace: {

&#x20;         tool\_calls: \[

&#x20;           {

&#x20;             id: 'call\_1',

&#x20;             name: 'geocode\_city',

&#x20;             arguments: { city: 'Seattle, WA' },

&#x20;           },

&#x20;           {

&#x20;             id: 'call\_2',

&#x20;             name: 'get\_weather',

&#x20;             arguments: {

&#x20;               latitude: 47.6062,

&#x20;               longitude: -122.3321,

&#x20;               date: '2026-09-03',

&#x20;               unit: 'celsius',

&#x20;             },

&#x20;           },

&#x20;         ],

&#x20;         tool\_results: \[

&#x20;           {

&#x20;             tool\_call\_id: 'call\_1',

&#x20;             output: { latitude: 47.6062, longitude: -122.3321 },

&#x20;           },

&#x20;         ],

&#x20;       },

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       geocode\_tool\_is\_relevant: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Is `trace.tool\_calls\[0].name` an appropriate tool for resolving `request.location`?',

&#x20;       },

&#x20;       geocode\_location\_matches: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `trace.tool\_calls\[0].arguments.city` match `request.location`?',

&#x20;       },

&#x20;       geocode\_arguments\_match\_schema: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `trace.tool\_calls\[0].arguments` conform to `available\_tools.geocode\_city.parameters`?',

&#x20;       },

&#x20;       geocode\_result\_matches\_call: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `trace.tool\_results\[0].tool\_call\_id` match `trace.tool\_calls\[0].id`?',

&#x20;       },

&#x20;       weather\_tool\_is\_relevant: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Is `trace.tool\_calls\[1].name` an appropriate tool for answering `request.text`?',

&#x20;       },

&#x20;       weather\_arguments\_match\_schema: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `trace.tool\_calls\[1].arguments` conform to `available\_tools.get\_weather.parameters`?',

&#x20;       },

&#x20;       weather\_uses\_geocoded\_coordinates: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Do the coordinates in `trace.tool\_calls\[1].arguments` match those in `trace.tool\_results\[0].output`?',

&#x20;       },

&#x20;       weather\_date\_matches: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `trace.tool\_calls\[1].arguments.date` match `request.date`?',

&#x20;       },

&#x20;       weather\_unit\_matches: {

&#x20;         type: 'noul',

&#x20;         instructions:

&#x20;           'Does `trace.tool\_calls\[1].arguments.unit` match `request.unit`?',

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />

&#x20;   </Accordion>

&#x20; </Step>



&#x20; <Step title="Use structure in the questions">

&#x20;   Keep questions short. `instructions` and `criteria` are usually strings, and for a short, unambiguous question a string is all you need. They can also be objects or arrays. Put the question in one field and the data that guides the question in the others.



&#x20;   Structure helps in these situations:



&#x20;   \* The question needs context or examples. A long sentence of background information or a list of example inputs belongs in named fields next to the question, where your code can add to them or swap them without rewriting the question.

&#x20;   \* Part of the question comes from your code. When a value comes from a database, put it in its own field instead of splicing it into a string template.

&#x20;   \* Several questions have similar instructions. A request takes one state and can include multiple questions. Adding supplementary data can help make questions distinct.



&#x20;   <Accordion title="Example: reference a record from your code">

&#x20;     This Noul compares a resume in the state against a record from a candidate database. The record goes into `potential\_duplicate` as it is, and the question refers to it by name.



&#x20;     <TypesafeExample

&#x20;       title="questions"

&#x20;       display="questions"

&#x20;       example={{

&#x20;     state: {

&#x20;       resume: {

&#x20;         name: 'John Smith',

&#x20;         location: 'Oakland, CA',

&#x20;         summary: 'Backend engineer with eight years of Python and Go experience.',

&#x20;         experience: \[

&#x20;           { employer: 'Google', title: 'Senior Backend Engineer', years: '2021-2025' },

&#x20;           { employer: 'Microsoft', title: 'Software Engineer', years: '2017-2021' },

&#x20;         ],

&#x20;       },

&#x20;     },

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       same\_as\_record\_18: {

&#x20;         type: 'noul',

&#x20;         instructions: {

&#x20;           potential\_duplicate: { name: 'John Smith', location: 'Oakland, California', last\_employer: 'Google' },

&#x20;           question: 'Is the resume for the same person as `potential\_duplicate`?',

&#x20;         },

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />

&#x20;   </Accordion>



&#x20;   The "potential\\\_duplicate" data sourced from code can change over time. The "question" references it using backticks.



&#x20;   The descriptions inside `criteria` can be objects too. For a Choice, each option's description can be an object that says what the option covers, what belongs to a different option, and a few examples. Use the same field names across options so the model can compare them directly.



&#x20;   <Accordion title="Example: define contrastive Choice criteria">

&#x20;     <TypesafeExample

&#x20;       title="questions"

&#x20;       display="questions"

&#x20;       example={{

&#x20;     state: 'How many disposable virtual cards can I make per day?',

&#x20;     selectedModels: \['jev-latest'],

&#x20;     questions: {

&#x20;       card\_help\_topic: {

&#x20;         type: 'choice',

&#x20;         instructions: {

&#x20;           question:

&#x20;             'Which disposable virtual card topic is the user asking about?',

&#x20;           focus: 'Classify the information the user wants.',

&#x20;         },

&#x20;         criteria: {

&#x20;           get\_disposable\_virtual\_card: {

&#x20;             what: 'Purpose, eligibility, or setup',

&#x20;             not\_for: 'Quantity, transaction, or merchant restrictions',

&#x20;             examples: \[

&#x20;               'How can I get a disposable virtual card?',

&#x20;               'What are disposable cards for?',

&#x20;             ],

&#x20;           },

&#x20;           disposable\_card\_limits: {

&#x20;             what: 'Quantity, transaction, or merchant restrictions',

&#x20;             not\_for: 'Purpose, eligibility, or setup',

&#x20;             examples: \[

&#x20;               'How many disposable cards can I make per day?',

&#x20;               'Where can I use a disposable card?',

&#x20;             ],

&#x20;           },

&#x20;         },

&#x20;       },

&#x20;     },

&#x20;   }}

&#x20;     />

&#x20;   </Accordion>



&#x20;   Each question type's page has a worked example:



&#x20;   \* \[Noul](/primitives/noul#structured-instructions) compares one resume against several candidate records, one question per record, with the questions built in code.

&#x20;   \* \[Choice](/primitives/choice#structured-instructions-and-criteria) describes two easily confused options with what each covers, what it's not for, and examples.

&#x20;   \* \[Score](/primitives/score#structured-level-descriptions) gives each level a description and example situations.



&#x20;   The \[structured-data-extraction cascade cookbook](/cookbooks/sde\_cascade) shows the shared-wording case, asking the same battery of questions about every field of an extracted record.



&#x20;   A short, unambiguous question or criterion can remain a string. Add structure when it separates guidance that would otherwise blur together. For the full set of places structure is accepted, see \[Advanced: structure](/primitives/advanced).

&#x20; </Step>



&#x20; <Step title="Ask a lot of questions">

&#x20;   Ask many narrow, independent questions about the same state in one request. This is how you maximize effectiveness and intelligence per dollar with the API: questions run in parallel, and code can combine their signals without adding serial model round trips.



&#x20;   See the \[Speculative Fan-Out pattern](/patterns/fan-out) and \[Parallel questions cookbook](/cookbooks/parallel\_questions).

&#x20; </Step>



&#x20; <Step title="Combine question outputs in code (or feed into a classical ML model)">

&#x20;   Combine independent answers with deterministic rules or weighted sums. For learned composition, use the probabilities as features in a downstream classical machine-learning model.



&#x20;   <Accordion title="Example: combine signals with a weighted score">

&#x20;     ```python theme={null}

&#x20;     answers = response.answers



&#x20;     # Combine independent signals into one application-specific score.

&#x20;     quality = (

&#x20;         0.4 \* answers\["answers\_request"].noul

&#x20;         + 0.4 \* answers\["citations\_are\_supported"].noul

&#x20;         + 0.2 \* (1 - answers\["contradicts\_context"].noul)

&#x20;     )

&#x20;     ```

&#x20;   </Accordion>



&#x20;   \[Composite Scoring](/patterns/composite-scoring) shows how to preserve individual judgments while combining them. If you do not have labels for a downstream model, use an ensemble of expensive reasoning models to generate them; the \[AutoResearch cookbook](/cookbooks/autoresearch\_feature\_discovery) shows how to train a classical model on System One outputs.

&#x20; </Step>



&#x20; <Step title="Route on uncertainty">

&#x20;   Make code take different actions for confident and unconfident answers. Escalate uncertain cases to a person or a more expensive reasoning model. Test thresholds by plotting confidence against accuracy on your data.



&#x20;   <Accordion title="Example: route by confidence">

&#x20;     ```python theme={null}

&#x20;     answer = response.answers\["card\_help\_topic"]



&#x20;     if answer.confidence < 0.8:

&#x20;         route\_to\_human\_review(ticket)

&#x20;     else:

&#x20;         route\_to\_handler(answer.choice, ticket)

&#x20;     ```

&#x20;   </Accordion>



&#x20;   See \[Confidence](/confidence) and \[Confidence-Gated Routing](/patterns/confidence-routing) for choosing thresholds and matching them to the risk of each action.

&#x20; </Step>

</Steps>



<Tip>

&#x20; Decomposition does not require more round trips. Questions over the same state run in parallel.

</Tip>



\## Putting it all together



This support-ticket workflow keeps deterministic work in code, sends only relevant structured context, evaluates many atomic questions in one request, and composes the answers with explicit confidence gates.



```python title="triage\_ticket.py" theme={null}

from typesafe\_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient





def triage\_ticket(ticket, customer):

&#x20;   # Handle deterministic states without calling a model.

&#x20;   if ticket\["status"] == "closed":

&#x20;       return "no\_action"



&#x20;   open\_orders = \[

&#x20;       order for order in customer\["orders"] if order\["status"] != "delivered"

&#x20;   ]



&#x20;   # Include only the structured context needed by the questions below.

&#x20;   state = {

&#x20;       "ticket": {

&#x20;           "message": ticket\["message"],

&#x20;           "sender": ticket\["sender"],

&#x20;           "links": ticket\["links"],

&#x20;       },

&#x20;       "customer": {

&#x20;           "plan": customer\["plan"],

&#x20;           "open\_orders": open\_orders,

&#x20;       },

&#x20;       "policy": {

&#x20;           "sensitive\_credentials": \["password", "security code", "API key"],

&#x20;       },

&#x20;   }



&#x20;   # Ask structured, atomic questions together so they run in parallel.

&#x20;   questions = {

&#x20;       "topic": Choice(

&#x20;           instructions={

&#x20;               "question": "Which team should handle `ticket.message`?",

&#x20;               "focus": "Classify the customer's primary request.",

&#x20;           },

&#x20;           criteria={

&#x20;               "billing": {

&#x20;                   "what": "Charges, invoices, refunds, or subscriptions",

&#x20;                   "not\_for": "Order tracking or account access",

&#x20;                   "examples": \["I was charged twice", "Where is my refund?"],

&#x20;               },

&#x20;               "orders": {

&#x20;                   "what": "Order status, delivery, cancellation, or returns",

&#x20;                   "not\_for": "Charges or account access",

&#x20;                   "examples": \["Where is my order?", "Cancel my shipment"],

&#x20;               },

&#x20;               "account": {

&#x20;                   "what": "Login, profile, permissions, or security",

&#x20;                   "not\_for": "Charges or order tracking",

&#x20;                   "examples": \["Reset my password", "I cannot sign in"],

&#x20;               },

&#x20;           },

&#x20;       ),

&#x20;       "requests\_credentials": Noul(

&#x20;           instructions={

&#x20;               "question": "Does the message request a sensitive credential?",

&#x20;               "compare": \[

&#x20;                   "`ticket.message`",

&#x20;                   "`policy.sensitive\_credentials`",

&#x20;               ],

&#x20;               "focus": "Look for a request to disclose the credential itself.",

&#x20;           },

&#x20;           criteria=NoulCriteria(

&#x20;               true={

&#x20;                   "what": "Asks the recipient to disclose a listed credential",

&#x20;                   "examples": \[

&#x20;                       "Reply with your password",

&#x20;                       "Send us your API key",

&#x20;                   ],

&#x20;               },

&#x20;               false={

&#x20;                   "what": "Does not ask the recipient to disclose a credential",

&#x20;                   "not\_for": "A legitimate instruction to reset a credential",

&#x20;                   "examples": \["Use this link to reset your password"],

&#x20;               },

&#x20;           ),

&#x20;       ),

&#x20;       "sender\_identity\_mismatch": Noul(

&#x20;           instructions={

&#x20;               "question": "Does the claimed sender identity conflict with its domain?",

&#x20;               "compare": \[

&#x20;                   "`ticket.sender.display\_name`",

&#x20;                   "`ticket.sender.email`",

&#x20;               ],

&#x20;               "focus": "Compare the named organization with the email domain.",

&#x20;           },

&#x20;           criteria=NoulCriteria(

&#x20;               true={

&#x20;                   "what": "Claims an organization unrelated to the email domain",

&#x20;                   "examples": \["Acme Payroll sent from claim-bonus.example"],

&#x20;               },

&#x20;               false={

&#x20;                   "what": "The identity and domain agree or make no conflicting claim",

&#x20;                   "examples": \["Acme Payroll sent from acme.example"],

&#x20;               },

&#x20;           ),

&#x20;       ),

&#x20;       "unexpected\_reward": Noul(

&#x20;           instructions={

&#x20;               "question": "Does the message announce an unexpected reward?",

&#x20;               "inspect": "`ticket.message`",

&#x20;               "focus": "Look for an unsolicited prize, payment, or reward claim.",

&#x20;           },

&#x20;           criteria=NoulCriteria(

&#x20;               true={

&#x20;                   "what": "Announces an unrequested prize, payment, or reward",

&#x20;                   "examples": \["You were selected for a $1,000 bonus"],

&#x20;               },

&#x20;               false={

&#x20;                   "what": "Contains no reward claim or discusses an expected payment",

&#x20;                   "not\_for": "A customer asking about a known refund or payroll deposit",

&#x20;                   "examples": \["When will my approved refund arrive?"],

&#x20;               },

&#x20;           ),

&#x20;       ),

&#x20;       "refund\_requested": Noul(

&#x20;           instructions={

&#x20;               "question": "Does the customer explicitly request a refund or credit?",

&#x20;               "inspect": "`ticket.message`",

&#x20;               "focus": "Require a requested remedy, not a billing complaint alone.",

&#x20;           },

&#x20;           criteria=NoulCriteria(

&#x20;               true={

&#x20;                   "what": "Directly asks for money back or an account credit",

&#x20;                   "examples": \["Please refund the duplicate charge"],

&#x20;               },

&#x20;               false={

&#x20;                   "what": "Does not ask for a refund or credit",

&#x20;                   "not\_for": "A complaint or billing question without a requested remedy",

&#x20;                   "examples": \["Why was I charged twice?"],

&#x20;               },

&#x20;           ),

&#x20;       ),

&#x20;       "mentions\_open\_order": Noul(

&#x20;           instructions={

&#x20;               "question": "Does the message refer to a supplied open order?",

&#x20;               "compare": \[

&#x20;                   "`ticket.message`",

&#x20;                   "`customer.open\_orders`",

&#x20;               ],

&#x20;               "focus": "Match an order id or other identifying details.",

&#x20;           },

&#x20;           criteria=NoulCriteria(

&#x20;               true={

&#x20;                   "what": "Refers to an open order by id or identifying details",

&#x20;                   "examples": \["Where is order A-104?"],

&#x20;               },

&#x20;               false={

&#x20;                   "what": "Does not identify any supplied open order",

&#x20;                   "not\_for": "A generic order question with no matching details",

&#x20;                   "examples": \["How long does shipping usually take?"],

&#x20;               },

&#x20;           ),

&#x20;       ),

&#x20;       "frustration": Score(

&#x20;           instructions={

&#x20;               "question": "How frustrated does the customer appear?",

&#x20;               "inspect": "`ticket.message`",

&#x20;               "focus": "Judge expressed frustration, not issue severity.",

&#x20;           },

&#x20;           criteria=\[

&#x20;               {

&#x20;                   "what": "Calm and matter-of-fact",

&#x20;                   "signals": \["Neutral wording", "No complaint about the experience"],

&#x20;               },

&#x20;               {

&#x20;                   "what": "Frustrated but civil",

&#x20;                   "signals": \["Expresses annoyance", "Remains constructive"],

&#x20;               },

&#x20;               {

&#x20;                   "what": "Very angry or threatening to leave",

&#x20;                   "signals": \["Hostile language", "Threatens cancellation or churn"],

&#x20;               },

&#x20;           ],

&#x20;       ),

&#x20;   }



&#x20;   with TypeSafeClient() as client:

&#x20;       response = client.system\_one(

&#x20;           state=state,

&#x20;           questions=questions,

&#x20;       )



&#x20;   # Compose independent spam signals with weights controlled by code.

&#x20;   answers = response.answers

&#x20;   spam\_risk = (

&#x20;       0.45 \* answers\["requests\_credentials"].noul

&#x20;       + 0.30 \* answers\["sender\_identity\_mismatch"].noul

&#x20;       + 0.25 \* answers\["unexpected\_reward"].noul

&#x20;   )



&#x20;   # Escalate uncertain judgments instead of guessing.

&#x20;   spam\_is\_uncertain = 0.4 < spam\_risk < 0.6

&#x20;   if spam\_is\_uncertain or answers\["topic"].confidence < 0.75:

&#x20;       return route\_to\_human\_review(ticket)

&#x20;   if spam\_risk >= 0.6:

&#x20;       return quarantine\_as\_spam(ticket)



&#x20;   # Let code decide which speculative answers matter on this path.

&#x20;   if answers\["topic"].choice == "billing":

&#x20;       return route\_to\_billing(

&#x20;           ticket,

&#x20;           refund\_requested=answers\["refund\_requested"].noul >= 0.7,

&#x20;       )

&#x20;   if answers\["topic"].choice == "orders":

&#x20;       return route\_to\_orders(

&#x20;           ticket,

&#x20;           mentions\_open\_order=answers\["mentions\_open\_order"].noul >= 0.7,

&#x20;       )



&#x20;   priority = (

&#x20;       "high"

&#x20;       if answers\["frustration"].confidence >= 0.7

&#x20;       and answers\["frustration"].score >= 1.5

&#x20;       else "normal"

&#x20;   )

&#x20;   return route\_to\_account\_support(ticket, priority=priority)

```

