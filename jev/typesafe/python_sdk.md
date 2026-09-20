> ## Documentation Index

> Fetch the complete documentation index at: https://docs.typesafe.ai/llms.txt

> Use this file to discover all available pages before exploring further.



\# TypeSafe Python SDK



> Install the TypeSafe Python SDK and get started with asynchronous or synchronous API calls.



<a id="typesafe-python-sdk" />



Browse the \[Python SDK source on GitHub](https://github.com/typesafe-ai/typesafe-sdk-python).



Asynchronous and synchronous Python clients for the \[TypeSafe](https://typesafe.ai) API. Learn how to use TypeSafe \[here](https://docs.typesafe.ai/).



<h2 id="quickstart">

&#x20; Quickstart

</h2>



1\. Install the SDK:



&#x20;  <Tabs>

&#x20;    <Tab title="uv">

&#x20;      ```sh theme={null}

&#x20;      uv add typesafe-sdk

&#x20;      ```

&#x20;    </Tab>



&#x20;    <Tab title="pip">

&#x20;      ```sh theme={null}

&#x20;      pip install typesafe-sdk

&#x20;      ```

&#x20;    </Tab>

&#x20;  </Tabs>

2\. Set `TYPESAFE\_API\_KEY` in your environment (create it \[here](https://console.typesafe.ai/))

3\. Call the System One API:



&#x20;  <Tabs>

&#x20;    <Tab title="Async">

&#x20;      With \[AsyncTypeSafeClient](/sdk/python/api/clients/async):



&#x20;      ```python theme={null}

&#x20;      from typesafe\_sdk import AsyncTypeSafeClient, Choice, Noul, Score





&#x20;      async def main() -> None:

&#x20;          async with AsyncTypeSafeClient() as client:

&#x20;              response = await client.system\_one(

&#x20;                  state={"document": "I was charged twice. Please fix this ASAP."},

&#x20;                  questions={

&#x20;                      "billing": Noul(instructions="Is this ticket about billing?"),

&#x20;                      "tone": Choice(

&#x20;                          instructions="What is the customer's tone?",

&#x20;                          criteria={"calm": None, "frustrated": None, "angry": None},

&#x20;                      ),

&#x20;                      "urgency": Score(

&#x20;                          instructions="How urgent is this ticket?",

&#x20;                          criteria=\["can wait", "this week", "today"],

&#x20;                      ),

&#x20;                  },

&#x20;              )



&#x20;          print(response.nouls\["billing"].noul)

&#x20;          print(response.choices\["tone"].choice)

&#x20;          print(response.scores\["urgency"].score)

&#x20;      ```

&#x20;    </Tab>



&#x20;    <Tab title="Sync">

&#x20;      With \[TypeSafeClient](/sdk/python/api/clients/sync):



&#x20;      ```python theme={null}

&#x20;      from typesafe\_sdk import Choice, Noul, Score, TypeSafeClient



&#x20;      with TypeSafeClient() as client:

&#x20;          response = client.system\_one(

&#x20;              state={"document": "I was charged twice. Please fix this ASAP."},

&#x20;              questions={

&#x20;                  "billing": Noul(instructions="Is this ticket about billing?"),

&#x20;                  "tone": Choice(

&#x20;                      instructions="What is the customer's tone?",

&#x20;                      criteria={"calm": None, "frustrated": None, "angry": None},

&#x20;                  ),

&#x20;                  "urgency": Score(

&#x20;                      instructions="How urgent is this ticket?",

&#x20;                      criteria=\["can wait", "this week", "today"],

&#x20;                  ),

&#x20;              },

&#x20;          )



&#x20;      print(response.nouls\["billing"].noul)

&#x20;      print(response.choices\["tone"].choice)

&#x20;      print(response.scores\["urgency"].score)

&#x20;      ```

&#x20;    </Tab>

&#x20;  </Tabs>



<h2 id="usage">

&#x20; Usage

</h2>



Learn more in the \[Usage guide](/sdk/python/usage).

