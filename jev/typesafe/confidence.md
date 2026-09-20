> ## Documentation Index

> Fetch the complete documentation index at: https://docs.typesafe.ai/llms.txt

> Use this file to discover all available pages before exploring further.



\# Confidence



> How TypeSafe reports certainty, how it differs from probability, and how to use it to control system behavior.



export function ConfidenceExplorer() {

&#x20; const \[probabilities, setProbabilities] = useState(\[90, 6, 4]);

&#x20; const options = \["A", "B", "C"];

&#x20; function changeProbability(index, value) {

&#x20;   setProbabilities(current => {

&#x20;     const others = \[0, 1, 2].filter(i => i !== index);

&#x20;     const remaining = 100 - value;

&#x20;     const previousRemaining = current\[others\[0]] + current\[others\[1]];

&#x20;     const next = \[...current];

&#x20;     next\[index] = value;

&#x20;     next\[others\[0]] = previousRemaining > 0 ? remaining \* current\[others\[0]] / previousRemaining : remaining / 2;

&#x20;     next\[others\[1]] = remaining - next\[others\[0]];

&#x20;     return next;

&#x20;   });

&#x20; }

&#x20; function formatProbability(value) {

&#x20;   if (Math.abs(value - 100 / 3) < 0.000001) return "33⅓%";

&#x20;   return `${Number(value.toFixed(1))}%`;

&#x20; }

&#x20; function choiceConfidence(values) {

&#x20;   const count = values.length;

&#x20;   const peak = Math.max(...values) / 100;

&#x20;   return Math.max(0, Math.min(1, (count \* peak - 1) / (count - 1)));

&#x20; }

&#x20; const confidence = choiceConfidence(probabilities);

&#x20; const maximum = Math.max(...probabilities);

&#x20; const winners = options.filter((option, i) => Math.abs(probabilities\[i] - maximum) < 0.000001);

&#x20; const selected = winners.length === 1 ? `Option ${winners\[0]}` : `Tie: ${winners.join(", ")}`;

&#x20; const buttonClass = "border px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pink-500";

&#x20; const buttonStyle = {

&#x20;   borderColor: "#71717a"

&#x20; };

&#x20; const eyebrow = {

&#x20;   fontSize: "0.6875rem",

&#x20;   fontWeight: 700,

&#x20;   letterSpacing: "0.08em",

&#x20;   textTransform: "uppercase"

&#x20; };

&#x20; return <section aria-label="Explore probabilities and confidence" className="not-prose my-6 border border-zinc-300 dark:border-zinc-700 p-5 sm:p-6 text-zinc-800 dark:text-zinc-200">

&#x20;     <div className="flex flex-wrap items-start justify-between gap-4">

&#x20;       <div>

&#x20;         <div className="text-zinc-600 dark:text-zinc-400" style={eyebrow}>Choice question with three options</div>

&#x20;         <div className="mt-2 text-base font-semibold">See how probability distribution changes confidence</div>

&#x20;       </div>

&#x20;       <div className="text-right" role="status" aria-live="polite" aria-atomic="true">

&#x20;         <div className="text-sm text-zinc-600 dark:text-zinc-400">Confidence</div>

&#x20;         <output className="block text-3xl font-semibold tabular-nums" style={{

&#x20;   color: "#E551BA"

&#x20; }}>

&#x20;           {confidence.toFixed(2)}

&#x20;         </output>

&#x20;       </div>

&#x20;     </div>



&#x20;     <div role="img" aria-label={`Probability distribution: ${options.map((option, i) => `${option} ${formatProbability(probabilities\[i])}`).join(", ")}. ${selected}.`} className="my-6">

&#x20;       <div className="text-xs text-zinc-600 dark:text-zinc-400">Probability</div>

&#x20;       <div aria-hidden="true" style={{

&#x20;   position: "relative",

&#x20;   height: "180px",

&#x20;   margin: "34px 0 36px 44px"

&#x20; }}>

&#x20;         {\[0, 50, 100].map(tick => <div key={tick} style={{

&#x20;   position: "absolute",

&#x20;   bottom: `${tick}%`,

&#x20;   width: "100%",

&#x20;   borderBottom: "1px solid",

&#x20;   borderColor: "color-mix(in srgb, currentColor 18%, transparent)"

&#x20; }}>

&#x20;             <span className="text-xs" style={{

&#x20;   position: "absolute",

&#x20;   right: "calc(100% + 8px)",

&#x20;   transform: "translateY(-50%)"

&#x20; }}>{tick}%</span>

&#x20;           </div>)}

&#x20;         <div style={{

&#x20;   position: "absolute",

&#x20;   inset: 0,

&#x20;   display: "flex",

&#x20;   justifyContent: "space-around",

&#x20;   alignItems: "flex-end"

&#x20; }}>

&#x20;           {options.map((option, index) => <div key={option} style={{

&#x20;   position: "relative",

&#x20;   width: "21%",

&#x20;   height: `${probabilities\[index]}%`

&#x20; }}>

&#x20;               <span className="text-sm font-semibold tabular-nums" style={{

&#x20;   position: "absolute",

&#x20;   bottom: "calc(100% + 6px)",

&#x20;   left: "50%",

&#x20;   transform: "translateX(-50%)",

&#x20;   whiteSpace: "nowrap"

&#x20; }}>{formatProbability(probabilities\[index])}</span>

&#x20;               <div style={{

&#x20;   height: "100%",

&#x20;   background: winners.length === 1 \&\& winners\[0] === option ? "#E551BA" : "currentColor",

&#x20;   opacity: winners.length === 1 \&\& winners\[0] === option ? 1 : 0.45

&#x20; }} />

&#x20;               <span className="text-sm" style={{

&#x20;   position: "absolute",

&#x20;   top: "calc(100% + 8px)",

&#x20;   left: "50%",

&#x20;   transform: "translateX(-50%)"

&#x20; }}>{option}</span>

&#x20;             </div>)}

&#x20;         </div>

&#x20;       </div>

&#x20;     </div>



&#x20;     <div className="space-y-3">

&#x20;       {options.map((option, index) => <label key={option} className="flex items-center gap-3 text-sm">

&#x20;           <span className="w-5 font-semibold">{option}</span>

&#x20;           <input type="range" min="0" max="100" step="1" value={probabilities\[index]} onChange={event => changeProbability(index, Number(event.target.value))} aria-label={`Probability of ${option}`} aria-valuetext={formatProbability(probabilities\[index])} className="min-w-0 flex-1 cursor-pointer" style={{

&#x20;   accentColor: "#E551BA",

&#x20;   minHeight: "44px"

&#x20; }} />

&#x20;           <output className="w-16 text-right tabular-nums">{formatProbability(probabilities\[index])}</output>

&#x20;         </label>)}

&#x20;     </div>

&#x20;     <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">Move a slider to change an option's probability. The other probabilities adjust to keep the total at 100%.</p>



&#x20;     <div className="mt-4 flex flex-wrap gap-2" aria-label="Example distributions">

&#x20;       <button type="button" className={buttonClass} style={buttonStyle} onClick={() => setProbabilities(\[90, 6, 4])}>Clear winner</button>

&#x20;       <button type="button" className={buttonClass} style={buttonStyle} onClick={() => setProbabilities(\[40, 33, 27])}>Spread out</button>

&#x20;       <button type="button" className={buttonClass} style={buttonStyle} onClick={() => setProbabilities(\[100 / 3, 100 / 3, 100 / 3])}>Even split</button>

&#x20;     </div>

&#x20;     <div className="mt-4 text-sm" aria-live="polite">{winners.length === 1 ? `Selected: ${selected}` : selected}</div>

&#x20;     <details className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">

&#x20;       <summary className="cursor-pointer">How this demo calculates Confidence</summary>

&#x20;       <p className="mt-3">TypeSafe computes confidence from how the probability is spread across the options. All of it on one option gives 1.0; the more evenly it spreads, the lower the confidence. This demo uses <code>(3 × largest probability − 1) / 2</code> to approximate confidence for three options.</p>

&#x20;     </details>

&#x20;   </section>;

}



All Score and Choice answers from TypeSafe include a `probabilities` property representing the probability distribution across the options (for Choice) or levels (for Score). The \*shape\* of that distribution is what tells you how certain the model is: concentrated on one outcome means a confident answer, spread out means an uncertain one.



The answer's `confidence` property collapses that shape into a single number from 0 to 1, so you can threshold on it without doing the math yourself. (Noul answers don't carry one.)



\## Confidence is derived from the probabilities



`confidence` is a statistic computed from the probability distribution the answer already gives you. TypeSafe computes it for you and returns it on every Choice and Score answer, so the common case needs no extra work on your side.



<ConfidenceExplorer />



<Note>

&#x20; \*\*A solid default:\*\* We provide `confidence` as a convenient measure that fits most use-cases, but you are never locked into our definition. Depending on what you are evaluating, a different measure may serve you better, which is exactly why we give you the full `probabilities` in the response. The pros and cons of different computations is a specialized topic that we'll keep to a separate cookbook rather than this page, and will add the link here when we do!

</Note>



For a \[Choice](/primitives/choice), the distribution is `probabilities` across your options. For a \[Score](/primitives/score), it is the distribution across your levels. In both cases a flatter distribution means lower confidence: low confidence on a Choice often means none of the options are a clear winner over the others, and low confidence on a Score often means the levels are ambiguous, multi-dimensional, or the state doesn't contain enough to go on.



\## "I don't know" is a useful signal



If an intelligent system, whether human or machine, cannot express honest uncertainty, the system cannot be trusted.



Confidence gives you a built-in mechanism for the model to say "I'm not sure about this one." This lets your code implement different behavior for different levels of certainty, which is the foundation for building systems you can actually rely on.



\## Three paths for using confidence in your code



A useful starting pattern is to divide confidence into three ranges, each producing a different system behavior:



\*\*High confidence:\*\* Act automatically. The model has a clear read and you can proceed without human involvement.



\*\*Medium confidence:\*\* Proceed with caution. The model has a reasonable answer but is not certain. Depending on context, you might ask the user to confirm, flag for review, or gather more information before acting.



\*\*Low confidence:\*\* Do not act. Route to a human, request clarification, or fall back to a different system. The model is telling you it does not have enough information or the question is not a good fit.



Where you draw those boundaries depends on the stakes.



\## Thresholds scale with risk



A confidence threshold is not one number. Different actions within the same system should be gated at different levels depending on the consequences of getting it wrong.



```python theme={null}

response = client.system\_one(

&#x20;   state=user\_message,

&#x20;   questions={

&#x20;       "action": Choice(

&#x20;           instructions="What is the user trying to do?",

&#x20;           criteria={

&#x20;               "check\_balance": "View account balance",

&#x20;               "approve\_transfer": "Approve the pending withdrawal request",

&#x20;               "support": "Get help with an issue",

&#x20;           },

&#x20;       ),

&#x20;   },

)



action = response.answers\["action"]

confidence = action.confidence



if confidence < 0.5:

&#x20;   # Model is genuinely unsure. Don't guess.

&#x20;   route\_to\_human(user\_message)



elif action.choice == "check\_balance":

&#x20;   # Low stakes. Showing the wrong screen is recoverable.

&#x20;   show\_balance(account\_id)



elif action.choice == "approve\_transfer":

&#x20;   if confidence > 0.9:

&#x20;       # High stakes, high confidence. Proceed with confirmation.

&#x20;       confirm\_then\_execute(account\_id)

&#x20;   else:

&#x20;       # High stakes, moderate confidence. Verify first.

&#x20;       ask\_user\_to\_confirm(account\_id)

```



The 0.5 confidence floor catches anything the model reports as genuinely uncertain. Above that, the threshold for acting without confirmation is higher for a destructive operation than for a read-only one. Your code encodes the risk tolerance.



<Note>

&#x20; The correct threshold values depend on your domain and the performance of the model for your use case. Start with conservative thresholds, test with your own data, and adjust as you observe results.

</Note>

