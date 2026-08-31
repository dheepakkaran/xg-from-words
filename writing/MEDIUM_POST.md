# I tried to predict football goals from commentary. I failed, and that failure led somewhere better.

*A story about expected goals, four hidden bugs, and a robot that watches football so I don't have to.*

---

## The thing that annoyed me

If you watch football, you have heard a commentator say this:

> "Liverpool have all the momentum now."

I wanted to know if that sentence means anything. Not as an opinion — as a number. If a team really has momentum, then a computer reading the commentary should be able to say *a goal is coming*, before the goal comes.

So I built it. And it did not work.

This post is about what happened next, because the failure turned out to be the useful part.

---

## First, two words you need

I will explain every short form as it appears. There are only a few, and none of them are hard.

**xG — expected goals.**
A number between 0 and 1 for a single shot. It answers one question: *if a hundred shots like this were taken, how many would go in?*

- A penalty is about **0.75** across this data. Out of 100 penalties, about 75 are scored. (In the Premier League alone it is 0.83 — better takers.)
- A shot from far outside the box is about **0.04**. Out of 100, about 4 go in.

Add up every shot a team takes and you get how much they *deserved* to score. That is why you sometimes hear "Arsenal won 1–0 but the xG was 0.4 to 2.1" — it means Arsenal won, and did not play better.

**AUC — Area Under the Curve.**
This is the score I use to say how good a model is. The full name is *area under the ROC curve*, and ROC stands for *Receiver Operating Characteristic*, which is a name from World War Two radar and tells you nothing. Ignore it.

Here is what AUC actually means, and it is simple:

> Take one shot that was a goal and one shot that was not. Show both to the model. **How often does it give the goal the higher number?**

- **0.50** — it is guessing. A coin toss.
- **1.00** — perfect, every single time.
- **0.78** — it gets the pair the right way round about 78 times in 100.

That is all. When I say "AUC 0.78", I mean: give it a goal and a miss, and 78% of the time it picks the goal.

---

## Where the data comes from, and why it matters

Real xG models are built from **cameras**. Companies put tracking cameras in stadiums and record where every player stood at the moment of every shot. That gives them the exact distance, the exact angle, and how many defenders were in the way.

That data costs money. A lot of money. If you are a student, or a small club, or you follow a league nobody sells data for, you cannot have it.

But every match also has **someone writing down what happened, in ordinary English, for free.**

```
"Attempt saved. Marcus Rashford (Manchester United) right footed shot
 from the centre of the box. Assisted by Bruno Fernandes with a cross."
```

Read that sentence again. It tells you where he shot from. Which foot. How the chance was made. That is *almost* what an xG model needs.

So my real question became:

> **How much of the expensive thing can you rebuild from the free words?**

I got the commentary from **ESPN's public API**. API means *Application Programming Interface* — a web address you can ask for data instead of a web page for humans. No key, no signup, no payment. I collected **87,980 shots** across **3,569 matches** and **six leagues**.

---

## Question one: can words predict the next goal?

I broke every match into moments. Every five minutes, from minute 10 to minute 80, I asked: *does either side score in the next fifteen minutes?*

That gave me **22,147 moments** from **1,491 Premier League matches** across four seasons.

Then I built two models on exactly the same moments:

- **The numbers.** Count the events so far — shots, corners, fouls, cards.
- **The words.** Just feed it the last ten lines of commentary as text.

Both come from the *same* commentary. The only thing that changes is whether I count it or read it. That matters — otherwise I would be comparing two different data sources, not two ways of reading one.

### The result

| What the model sees | AUC |
|---|---|
| Nothing — just guessing | 0.500 |
| **The words** | 0.513 |
| **The numbers** | 0.540 |
| Numbers + which two teams are playing | 0.565 |

The numbers beat the words. Every time, in every test I ran.

But look at those numbers again. **0.513 and 0.540.** A coin toss is 0.500. Neither model is doing much of anything.

So the honest answer was: *this does not work.* Which is where most projects stop.

---

## The trick that saved the project: measuring the ceiling

Here is the question that bothered me. When a model fails, there are two possible reasons:

1. **My model is bad.**
2. **The thing I am trying to predict is unpredictable.**

Those are completely different problems, and everyone assumes it is the first one. So they buy a bigger model, or more data, and get nowhere.

I decided to measure which one it was. And there is a clean way to do it:

> **Build a model that cheats.**

I gave a model the events from *inside* the fifteen minutes it was supposed to predict. Every shot, every corner, every foul that was about to happen. I removed only the goals themselves. This model has, effectively, **watched the future**, and is only being asked *who scored*.

It reached **0.602**.

Read that again. A model that has already seen the next fifteen minutes can only get to 0.60.

| Model | AUC | Share of what is possible |
|---|---|---|
| Guessing | 0.500 | — |
| The words | 0.513 | 13% |
| The numbers | 0.540 | 40% |
| **Cheating — sees the future** | **0.602** | **100%** |

So my model was not bad. **The target was nearly noise.** Whether a goal lands in a particular fifteen minutes comes down mostly to whether a shot goes in — and almost nothing before it tells you that.

That is a real finding. "It didn't work" is not. The difference is the ceiling.

**And one uncomfortable extra:** a model that knows *only which two teams are on the pitch* — nothing about the match in progress — scored **0.559**. Better than everything happening inside the match, combined. Arsenal at home are more likely to score in any fifteen minutes than Burnley away, and no amount of commentary changes that.

---

## The pivot

While measuring all this, I noticed something.

Commentary about **fouls and corners** is written from a template. The same handful of sentences, over and over. Across all 1,900 Premier League matches I have: **61** different sentence shapes for **79,345** foul lines, and 26 for 15,638 corners.

Commentary about **shots** is not. **2,341** different shapes for **16,941** missed shots, and 1,314 for 3,570 goals. Shot lines say body part, position on the pitch, how the chance was built.

Which is exactly what xG is made of.

So I asked a different question — and this is the important switch:

- ❌ *When will a goal come?* → depends on whether the shot goes in → **almost random**
- ✅ *Was that shot a good chance?* → depends on where and how it was struck → **knowable**

The first question is about luck. The second is about position. I had been asking the wrong one.

---

## Then the project nearly died

I fed the shot sentences to a model. It scored **1.0000**. Perfect. Every single shot, right.

I did not celebrate. A perfect score means something is wrong.

Here is what was wrong. Every shot's commentary **opens by saying what happened**:

```
"Goal! Chelsea 1, Everton 0. Nicolas Jackson..."   → always a goal
"Attempt missed. Luke Shaw..."                        → never a goal
"Attempt saved. Marcus Rashford..."                   → never a goal
"Attempt blocked. Kai Havertz..."                     → never a goal
```

The model was not learning football. **It was reading the first two words.** Like a student who found the answer key.

This has a name: **data leakage**. Information about the answer sneaking into the question. It is the single most common way a machine learning project quietly becomes worthless — because it does not look like a bug. It looks like success.

### Removing it took four attempts. Three of them failed.

**Attempt 1.** Cut the opening sentence. Still leaked — the penalty flag showed a 100% scoring rate, which is impossible.

**Attempt 2.** Cut the opener plus a list of words like "saved" and "missed". The text now *looked* completely clean. I read it myself and was satisfied.

It was still leaking. I only found out by printing what the model had learned — and the word **"goal"** was weighted higher than everything else combined. It had survived somewhere I had not looked. The 0.82 I got from that attempt was fake.

**Attempt 3.** Stop deleting; start keeping. Instead of removing bad phrases, I kept *only* phrases I had approved — the position, the foot, the assist. Nothing else gets through.

That looked right. It gave me my headline number. **It was still wrong.**

**Attempt 4** — found days later, by accident, while building a feature that shows similar past shots. The top-rated chance in the season was *"from a free kick right footed shot"* and **all forty** of its most similar past shots were goals. Forty out of forty is not football.

ESPN writes the two outcomes differently:

```
Scored:  "Olise (Palace) from a free kick with a left footed shot to..."
Missed:  "...shot from outside the box ... from a direct free kick"
```

The exact phrase that survived my approved list — *"from a free kick"* — appears **only when the free kick is scored.** 60 shots, all 60 goals.

So free kicks came out entirely. They cannot be identified from this data before the outcome is known. Even the event type gives it away.

**What I learned, and it is the main lesson of the whole project:**

> A list of forbidden words only catches the leaks you already thought of.

My test had a hand-written list. "Free kick" was never going to be on it, because a free kick is a perfectly normal thing to describe. So I replaced the list with a rule that asks the data instead:

> *Any phrase appearing 25 times or more that scores far above the penalty rate is not describing a chance. It is naming the outcome.*

That catches leaks I have not imagined. Run it against my old data and it flags the free kick immediately.

*(A fifth bug turned up the same way, from the same habit of tracing one real example end to end: my code was reading "headed" out of "assisted by X with a **headed** pass" and labelling 1,636 **footed** shots as headers. Those convert at 13.8%; real headers at 10.0%. One label was carrying two different things.)*

---

## The comparison — and what it actually means

Now the real test. Is my model any good compared to a **professional** one?

**StatsBomb** is a company that builds xG for real clubs from real tracking cameras. They publish one Premier League season openly, for free: **2015-16**.

So I pointed both models at the same **8,825 shots** and asked the same question.

Two things make this a hard test for me, not an easy one:

1. My model was trained on football from **2022 to 2025**. It was tested on **2015-16** — nine years earlier, a different era, different commentary writers. It had never seen anything from that season.
2. Their model had the season's own camera data in hand.

First, a sanity check that the two datasets really describe the same shots: they agree on **99.71%** of outcomes. Good — the join is real.

### Result 1: how often each picks the goal (AUC)

| Model | What it sees | AUC |
|---|---|---|
| **Mine** | one English sentence | **0.7826** |
| StatsBomb | exact coordinates, 16 player positions | 0.8118 |

Both are well above a coin toss. The gap is 0.029.

To put it in the plainest terms: measuring from 0.50 (guessing) as the floor,

```
mine   = 0.7826 - 0.50 = 0.2826
theirs = 0.8118 - 0.50 = 0.3118
ratio  = 0.2826 / 0.3118 = 90.6%
```

> **A sentence of English gets 90.6% of the way to a stadium full of cameras.**

### Result 2: how far each was from the truth, in goals

AUC is about ranking. This is about being *right*.

For each team in each match, I compared what the model expected to how many they actually scored, and took the average gap.

| Model | Average error |
|---|---|
| Mine, from words | **0.781 goals** |
| StatsBomb, from cameras | **0.740 goals** |

The commercial model is better by **0.041 of a goal** per team per match. That is the entire difference between reading a sentence and installing cameras.

### Result 3: a point system, because a table nobody reads settles nothing

Each side of each match is worth one point, to whichever model landed nearer the real goals. Within a twentieth of a goal, they share it.

```
StatsBomb  404 points
Mine       342 points
```

They were closer in **54.2%** of cases.

They win. Narrowly. On 373 matches they had camera data for and I had a sentence.

### What this comparison does and does not prove

**It proves:** words carry most of what matters about shot quality. Not all. Most.

**It does not prove** my model is better, or as good. It is not. It loses on every measure. The point is *by how little* — and that the thing it loses to costs money while mine does not.

**And what the gap is made of:** the 9.4% I cannot recover is exactly what a sentence never says. Distance in metres. The angle. How many defenders were in the way. No cleverer model can read information that was never written down.

I checked that last claim rather than assuming it — see below.

---

## Does it work anywhere else?

The whole argument is *commentary is free where cameras are not*. That only matters if the model travels.

So I took the model trained on **English** football and pointed it, with no retraining and no adjustment, at five other leagues.

| League | AUC |
|---|---|
| Premier League *(trained here)* | 0.7709 |
| La Liga (Spain) | 0.7730 |
| Serie A (Italy) | 0.7702 |
| Bundesliga (Germany) | 0.7795 |
| Ligue 1 (France) | 0.7807 |
| **Primeira Liga (Portugal)** | **0.7871** |

```
at home      0.7709
abroad, mean 0.7781
cost of moving  -0.0072   ← a small gain, not a loss
```

It does slightly *better* abroad than at home. It has never been told anything about Portuguese or German football.

Why does that work? Because it reads **the sentence**, and the company that writes those sentences writes them the same way everywhere. That is the whole argument in one table: camera data exists for a handful of competitions; commentary exists for hundreds.

---

## Six tools I was supposed to use, and did not

My original plan listed an impressive stack of technology. I measured each one instead of assuming, and dropped all six. Each has a script in the repository that reruns the measurement in seconds.

**Spark** — for data too big for one computer.
My entire dataset is **4 megabytes**. It loads in **0.04 seconds**. Even scraping every league ESPN has, for 25 years, would be about 15 GB. Spark is for thousands of gigabytes. It would be like hiring ten lorries to move one bag.

**A large language model, to read the sentences better than my code does.**
Worth testing, so I tested it — for free. I gave models the *entire* sentence instead of the 18 things my code pulls out of it.

| What the model sees | AUC |
|---|---|
| **18 extracted fields** | **0.7709** |
| Every 1-to-4 word phrase in the sentence | 0.7612 |
| A sentence-meaning model (MiniLM) | 0.7584 |

Reading more of the sentence is worth **minus 0.0097**. Everything that sees the whole text does *worse*. The rest of the sentence is player names and filler — noise. There is nothing left in there for a better reader to find, so a bigger model cannot help. I dropped it on that evidence, not on taste.

**vLLM** — software for running large language models fast on your own machine.
Its speed comes from a specific kind of NVIDIA graphics card. My laptop is a Mac and has none. Installing it would also downgrade libraries the working code depends on. It would run slower *and* break things.

**C++** — a faster programming language, for when Python cannot keep up live.
I measured before rewriting. The busiest window across six leagues has **14 matches at once**. Python takes **2.44 milliseconds** per match. The budget between checks is 15 seconds.

```
14 matches × 2.4 ms = 34 ms
that is 0.23% of the budget
```

And the thing that actually takes time is **waiting for ESPN to answer: 147 milliseconds.** The computing is **60 times cheaper than the wait**. No language change makes a website reply faster.

**Kubeflow** — for retraining a model on a schedule.
Only worth it if the model goes stale. I tested: a model trained on **2015-16** and used on **2025-26** — ten years old — loses **0.007 AUC**. One recent season is as good as three. There is nothing to retrain.

**LangGraph** — for orchestrating complicated multi-step AI flows.
After dropping the language model, my flow is: score the shot, check a threshold, look up similar shots, format a sentence. Four steps, one branch, no loops. That is an `if` statement.

**Why I am telling you what I did not build.** Adding a tool that earns nothing is not neutral. In an interview, "why did you use Spark?" has exactly one good answer, and "the job description mentioned it" is not it.

---

## How it runs itself

The project now watches football without me. Here is the whole design, and the one constraint that shapes it.

### The constraint

**The scheduler cannot read the fixture list.** GitHub lets me write fixed times into a file. I cannot say "wake up five minutes before the next match", because at the time I write the file, nobody knows when the next match is.

So I split it in two:

| | Job | Behaviour |
|---|---|---|
| **The alarm** | dumb | "wake up every hour" |
| **The script** | smart | "is a match actually on? is one about to start?" |

The fixture awareness lives in the script, not the schedule.

### What happens every hour

```
Wake up. Ask ESPN: is a match live?

  YES  → score every shot, write the result, look again in 60 seconds
  NO, but one starts within 45 minutes  → stay awake and wait
  NO, nothing coming  → go back to sleep (takes about 3 minutes)
```

### Tonight, for example

```
18:50 UTC   alarm rings. No match yet.
            Checks the calendar: "Aston Villa v Arsenal, in 10 minutes."
            Stays awake.

19:00       kick-off. Shots start arriving.
            Every 60 seconds: read the new commentary, score the shots,
            update the page, and record how old the commentary was.

20:45       full time. Three quiet checks. Goes to sleep.
```

I will be doing something else. My laptop can be closed. UTC means *Coordinated Universal Time*, the world clock that does not change for summer time — which becomes important in a moment.

### The bug that would have killed this silently

My first version woke at four fixed times: 11:25, 13:55, 16:25 and 18:55 UTC. It matched every August fixture. I was happy.

Then I checked properly, against all 361 remaining fixtures of the season.

Kick-off times across the season, and whether I covered them:

```
11:30 UTC     5 matches   covered
13:00 UTC     9 matches   MISSED
14:00 UTC    98 matches   covered
15:00 UTC   175 matches   MISSED
20:00 UTC    51 matches   MISSED
```

That 15:00 slot is the biggest in the calendar. **Covered: 119. Missed: 242** — 67% of the season.

**Why?** In late October the United Kingdom moves off summer time. A Saturday 3pm kick-off is 14:00 UTC in August and **15:00 UTC in November**. My alarms were in UTC and I had only looked at August.

Here is the part that should worry you more than the bug. **Nothing would have told me.** The job would wake, find no match, exit successfully, show a green tick — and from October the site would simply stop updating. Forever. Silently.

The fix: wake every hour through the hours football is played, and let the script decide. I then simulated all 361 fixtures: **every one is caught from kick-off, none mid-match.**

And that simulation is now a test, so it cannot rot.

---

## The tests, and what each one is actually guarding

**CI** stands for **Continuous Integration**. Strip away the jargon and it is this:

> A computer somewhere runs all my checks, automatically, every time I change the code.

The important part is that it uses a **fresh, empty computer every single time**. So "it works on my machine" cannot hide anything. Forget to list a library and it fails immediately.

I have **39 tests**. Here are the ones that exist because something actually went wrong.

**1. Can any feature see the future?**
Takes a real match, deletes everything after minute *M*, rebuilds the numbers, and demands they be **identical** to the ones built from the full match. Anything that can peek forward fails here.

**2. Does the label still change?**
Because test 1 could pass by doing nothing at all. If the answer never moves when I delete the future, the test is meaningless. This makes sure the test is testing something.

**3. Does the shot's outcome stay out of the text?**
Not by checking words — I tried that and it missed the free kick. It trains a model and demands it *cannot* score too well. If any new phrasing sneaks the answer back in, the score jumps and the build fails.

**4. Does the raw text still leak?**
The companion to test 3. If the unedited sentence stopped leaking, test 3 would be proving nothing.

**5. Is any phrase secretly the answer?**
The rule that replaced my hand-written list. Every phrase that appears 25+ times is checked, and anything scoring confidently above the penalty rate fails. This is the one that would have caught the free kick.

**6. Does the schedule actually catch the football?**
Reads the alarm times out of the workflow file and the kick-off times out of the calendar, and simulates all 361 remaining fixtures. The 67% bug cannot come back.

**7. Is anything stale?**
This one exists because I broke the same thing three times in a day, and never noticed:

- a committed test sample was older than the leagues I had added — so **CI passed while the tests failed on my own machine**
- a cache was older than a code change — so a feature ran on old numbers
- the website's data file was older than a rerun — so **the headline read 90.1% for two days after the real answer moved to 90.6%**

None of them raised an error. Each one quietly served an old number. So now there is a declared list of what is built from what, and a test that fails when the timestamps are out of order.

**8. Can the live path run on almost nothing?**
The match-watching job installs exactly one library. That is only true because the model ships as **plain numbers in a small text file** and is scored in about ten lines of arithmetic — no heavy machine learning libraries, no binary file I have to trust. The test hides all the heavy libraries and checks the live code still runs. An accidental import would break nothing else — it would break the job, at kick-off, in three weeks.

**9. Is any number on the website typed in by hand?**
This is the test that came from the 90.1% embarrassment. Every figure on the page must come from the generated data file. If a number is sitting loose in the text where it can go out of date, the build fails.

---

## What I am still not sure about

One claim in this project has **no evidence behind it at all**, and I would rather say so than let you assume otherwise.

Everything about reading a match live assumes the commentary arrives **fast enough to be worth reading**. I have never measured it, because no match was ever running at a moment when I could. A job now runs during kick-offs specifically to record it, and whatever it finds will go in the repository — including if the answer is "too slow to be useful".

---

## The short version

- **Commentary cannot tell you when a goal is coming.** I measured how unpredictable it is: even a model that has *watched the next fifteen minutes* only reaches 0.60. The problem is the football, not the model.
- **Commentary can tell you how good a chance was.** It reaches **90.6%** of a camera-based commercial model, tested on a season nine years outside anything it had seen.
- **The same model works in six countries** with no retraining, and slightly better abroad than at home.
- **It found four separate leaks**, three of which passed my own inspection. Each is now a test.
- **Six impressive tools were measured and dropped.** None of them earned a place.
- **It runs on its own**, hourly, through the whole season, and a test proves the schedule catches all 361 remaining matches.

**The thing I would actually want you to take away:** when a model fails, measure whether the problem is the model or the target. Almost nobody does. It is the difference between "my project didn't work" and "here is how unpredictable this actually is, with a number."

---

*Code and the full technical write-up:*
[github.com/dheepakkaran/xg-from-words](https://github.com/dheepakkaran/xg-from-words)

*The live page, which updates itself during matches:*
[dheepakkaran.github.io/xg-from-words](https://dheepakkaran.github.io/xg-from-words/)

*Data: ESPN's public commentary feed, and StatsBomb's open data.*

---

## Every short form used, in one place

| Short form | Full name | What it means here |
|---|---|---|
| **xG** | expected goals | Chance of a shot being scored, 0 to 1. Add them up for a team and you get how much they deserved to score |
| **AUC** | Area Under the Curve | Show the model one goal and one miss — how often does it pick the goal? 0.50 is guessing, 1.00 is perfect |
| **ROC** | Receiver Operating Characteristic | The curve AUC is the area under. A radar term from the 1940s. Safe to ignore |
| **CI** | Continuous Integration | A computer runs all your checks automatically, on a fresh machine, every time you change the code |
| **API** | Application Programming Interface | A web address that returns data instead of a web page |
| **JSON** | JavaScript Object Notation | The text format the data arrives in. Readable if you open it |
| **UTC** | Coordinated Universal Time | The world clock, with no summer-time changes. My schedule bug came from forgetting that the UK's clock *does* change |
| **BST / GMT** | British Summer Time / Greenwich Mean Time | The UK's two clocks. It switches between them in late October, which moved every kick-off by an hour |
| **cron** | (from *chronos*, Greek for time) | A list of fixed times at which a computer should run something |
| **Elo** | (named after Arpad Elo) | A rating for how strong a team is, from its past results. Chess uses it too |
| **TF-IDF** | Term Frequency – Inverse Document Frequency | A basic way to turn text into numbers: count the words, and weight down ones that appear everywhere |
| **MiniLM** | a small language model | Turns a sentence into a list of numbers that captures its meaning. Used here to test whether "understanding" the sentence beat extracting from it. It did not |
| **LLM** | Large Language Model | The kind of model behind ChatGPT. Tested, measured, dropped |
| **vLLM** | (v for *virtual*) | Software for running an LLM fast on your own hardware. Needs an NVIDIA graphics card, which I do not have |
| **GPU / CUDA** | Graphics Processing Unit / NVIDIA's toolkit for it | The hardware that makes large models fast, and the software that talks to it |
| **MAE** | Mean Absolute Error | The average gap between what you predicted and what happened. Mine: 0.781 goals. StatsBomb's: 0.740 |
| **Brier score** | (named after Glenn Brier) | Like MAE, but it punishes confident wrong answers harder |
| **log loss** | logarithmic loss | Punishes confident wrong answers *very* hard. Useful because I need honest percentages, not just correct rankings |
| **data leakage** | — | When information about the answer sneaks into the question. Makes a broken model look perfect. I found four |
| **HTTP 403 / 404** | Forbidden / Not Found | Website error codes. FBref returned 403 — blocked. This is why I could not use their xG |
