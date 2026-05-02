# The Karpathy Doctrine — Three Evaluation Layers (Deep Dive)

> *"Don't try to be a good researcher. Try to work on important, interesting problems, and understand them deeply."*

A three-layer filter for doing serious AI and software work. Distilled from 'Software 2.0' (Medium, 2017), 'A Recipe for Training Neural Networks' (karpathy.github.io, 2019), 'Neural Networks: Zero to Hero' YouTube series (2022-2023), 'State of GPT' at Microsoft Build (2023), Lex Fridman #333 and #452, the nanoGPT/micrograd/minbpe/llm.c GitHub repos, and the full @karpathy Twitter/X corpus.

**40 doctrines across 3 layers.** Every doctrine carries a *rule*, a concrete *test*, and its *source*.

---

## Layer 1 — Problem-Selection Taste *(11 doctrines)*
*What is worth working on at all.*

Karpathy's problem-selection doctrine is organized around one foundational idea: Software 2.0. The most important problems are those where neural networks replace hand-written code — where the software is learned from data rather than explicitly programmed. Within that frame, the highest-leverage work is at the infrastructure layer: the tools, methods, and mental models that allow the entire field to move faster.

### From 'Software 2.0' and the Zero to Hero philosophy

- **Software 2.0 — The Paradigm Shift** *(Software 2.0, Medium, November 2017)* — Software 1.0 is code that humans write. Software 2.0 is code (neural network weights) written by optimization over data. Every domain where Software 2.0 can replace Software 1.0 is undergoing the most important software transition in decades.
- **Work on Infrastructure That Benefits the Entire Field** *(nanoGPT GitHub; Lex Fridman #333; Zero to Hero series)* — The highest-leverage contribution makes it easier for everyone to do the important work. Tools that accelerate 1,000 researchers are worth more than research that advances one person's understanding.
- **Build From Scratch to Understand** *(Neural Networks: Zero to Hero, 2022-2023; micrograd repo)* — The only way to genuinely understand a complex system is to build it from scratch. Build micrograd (autograd in 25 lines), then makemore, then nanoGPT. Each level builds on the previous and you understand every line.
- **The Tight Feedback Loop Imperative** *(A Recipe for Training Neural Networks, 2019; Zero to Hero)* — Problems where you can iterate in minutes rather than days compound learning faster. The feedback loop speed is a direct multiplier on your learning rate.
- **Work on Problems Where Intuition Is Still Being Built** *(Karpathy talks on deep learning intuition; Lex Fridman #452)* — Mature problems have accumulated intuition. Emerging problems have none. Building intuition in a new domain is among the highest-leverage activities because your insights become the field's starting point.
- **Pick Problems Where the Simplest Implementation Teaches the Most** *(micrograd repo, 2020; nanoGPT repo, 2022; Zero to Hero)* — Problems that can be illuminated by a 500-line implementation are more valuable as teaching tools than those requiring 500,000 lines. The minimal implementation that demonstrates the key principle is both a research tool and an educational one.
- **The 'Can I Implement It From Scratch?' Test** *(Zero to Hero series; nanoGPT repo; Karpathy teaching discussions)* — The deepest test of understanding is implementation. Reading a paper and understanding it are different things. Implement the paper from scratch, match the results, understand every design choice.
- **Inspect Your Data Before Your Model** *(A Recipe for Training Neural Networks, 2019; Zero to Hero)* — The most common and costly mistake in machine learning is optimizing the model when the problem is in the data. Look at your data first, always. More data of worse quality is usually worse than less data of better quality.
- **LLMs as the New Operating System Layer** *(State of GPT, Microsoft Build 2023; Hacker's Guide to Language Models, 2023)* — Large language models are becoming the new operating system layer for software applications. This architectural shift creates the same kind of platform opportunity that operating systems created in the 1980s.
- **The Education Multiplier** *(Zero to Hero series; cs231n Stanford; Lex Fridman #333)* — Teaching is among the highest-leverage activities in technology. Each person who deeply understands neural networks can produce years of compounded research impact. The student who truly understands the fundamentals produces better work than one who learned only from tutorials.
- **Work on the Bottleneck, Not the Solved Part** *(A Recipe for Training Neural Networks, 2019; Tesla AI Day 2021)* — Every AI system has a bottleneck whose improvement would most increase overall performance. Most researchers work on parts they find interesting, not the bottleneck. Identify the true bottleneck first (often data, not model).

---

## Layer 2 — Approach Taste *(19 doctrines)*
*Given the problem, which angle to attack from.*

Karpathy's approach doctrine is built around one core discipline: empirical rigor. Intuitions must be tested; results must be visualized; assumptions must be challenged. The 'Recipe for Training Neural Networks' is the canonical statement — a systematic protocol for debugging and improving neural networks that generalizes to any empirical machine learning work.

### From 'A Recipe for Training Neural Networks' (2019)

- **The Recipe: Become One With the Data First** *(A Recipe for Training Neural Networks, 2019)* — Before writing a single line of model code: examine your data. Understand the distribution, find the outliers, identify mislabeled examples, count the classes. This step is always skipped and always matters.
- **Overfit a Single Batch First** *(A Recipe for Training Neural Networks, 2019)* — Before training on the full dataset, train on a single batch of 5-10 examples until loss goes to near-zero. This verifies that your model can learn at all. If you can't overfit one batch, something is broken.
- **Visualize Everything** *(A Recipe for Training Neural Networks, 2019; Zero to Hero)* — Loss curves, activation distributions, gradient magnitudes, attention patterns, failure cases — you cannot debug what you cannot see. Instrument your training pipeline to make every important quantity observable.
- **The Baby Model Protocol** *(A Recipe for Training Neural Networks, 2019; nanoGPT design philosophy)* — Before training the full model, train a minimal version. Debug on the small model first. The small model trains faster, costs less, and reveals the same class of bugs. Never debug large models when small models are available.
- **The Learning Rate Is the Most Important Hyperparameter** *(A Recipe for Training Neural Networks, 2019)* — Too high = loss explodes; too low = too slow to converge; wrong schedule = premature convergence. Always use a learning rate finder before committing to a long training run.
- **Use the Loss Curve as the Primary Diagnostic** *(A Recipe for Training Neural Networks, 2019)* — Loss not decreasing: learning rate too low or data problem. Loss oscillating: learning rate too high. Loss plateauing: model or dataset too small. Read the loss curve before changing anything.
- **The Dead Neuron Diagnostic** *(A Recipe for Training Neural Networks, 2019; cs231n)* — In ReLU networks, monitor the fraction of neurons with non-zero activations. If more than 30% are dead after initialization, adjust your initialization or learning rate.
- **Inspect Failures, Not Just Successes** *(A Recipe for Training Neural Networks, 2019; Tesla AI Day 2021)* — Sample from the worst-performing examples and look at them manually. The pattern in failures tells you what the model is missing, what the data is missing, or what the problem formulation is wrong about.
- **The Gradient Flow Audit** *(A Recipe for Training Neural Networks, 2019; cs231n)* — Monitor gradient norms layer-by-layer during training. If early layer gradients are 100x smaller than late layer gradients, you have gradient vanishing.
- **The Numerical Stability Check** *(A Recipe for Training Neural Networks, 2019)* — Add numerical stability checks throughout your code: assert that loss is finite, that gradients are finite, that weights are finite. Catch instability early before it corrupts a long training run.

### From the Zero to Hero philosophy and nanoGPT design

- **Write Minimal, Readable Code** *(nanoGPT repo; micrograd repo; llm.c repo; Karpathy coding philosophy)* — No abstractions beyond what the problem requires, explicit variable names, clear data flow. Complexity is the enemy of understanding. Never add an abstraction before you've used the primitive 3 times.
- **Read Papers AND Implement Them** *(Karpathy's approach to learning; Zero to Hero philosophy)* — Reading a paper produces surface-level understanding. Implementing the paper — getting it to work, matching reported results, debugging the gaps — produces deep understanding.
- **Teach to Learn** *(Zero to Hero series philosophy; Karpathy on teaching as learning)* — The act of explaining a concept clearly reveals gaps in your own understanding. The Zero to Hero series is a discipline of verification: if you can explain it to a non-expert, you truly understand it.
- **The Baseline Before the Innovation** *(A Recipe for Training Neural Networks, 2019; ML research methodology)* — Before proposing a novel approach, establish a strong baseline with the simplest possible method. Many 'improvements' disappear when compared against a properly tuned simple method.
- **Run Experiments in Public** *(Zero to Hero series; nanoGPT and micrograd release philosophy)* — Publishing code, findings, and experiments publicly — before they're polished — accelerates the field and builds your reputation. The internet will improve your rough work faster than you will alone.
- **The Simplest Working Architecture First** *(A Recipe for Training Neural Networks, 2019; nanoGPT design)* — Start with the simplest architecture that could possibly work. Add complexity only when you have evidence that simpler isn't sufficient. Every unnecessary layer is a debugging surface you don't need.
- **Work With the Best Environment** *(Zero to Hero series; cs231n notes)* — GPU availability, fast data loading, efficient logging, and reproducible experiments are the infrastructure that makes research fast. Fix the bottleneck before doing more experiments with the bottleneck in place.
- **Work in Public With the Best** *(Lex Fridman #333; Lex Fridman #452)* — The fastest way to improve is to work alongside the best researchers in the world. The intellectual density of your environment is the primary determinant of growth rate.
- **The Right Size of Problem Requires Iteration** *(Karpathy research approach; Zero to Hero development process)* — Run many small experiments fast, kill the ones that don't show promise immediately, and invest deeply only in the promising directions. Most experiment ideas are wrong.

---

## Layer 3 — Stopping Taste *(10 doctrines)*
*When to abandon, when to push, when done enough.*

Karpathy's stopping doctrine is empirical: stop when the data says stop, not when intuition says stop. Loss curves plateau? Stop and diagnose before continuing. The paradigm has shifted? Stop investing in the obsolete one.

### From 'A Recipe for Training Neural Networks' and the paradigm shift record

- **Stop When Loss Plateaus — Diagnose Before Continuing** *(A Recipe for Training Neural Networks, 2019)* — A loss plateau is information: the model has learned everything it can from the current data with the current architecture. Diagnose (capacity? data? optimizer?) before continuing. More training on a plateau teaches you nothing.
- **Stop Optimizing Hyperparameters Before Understanding Data** *(A Recipe for Training Neural Networks, 2019)* — Hyperparameter tuning on a bad dataset produces a model that is optimally fit to the wrong problem. Stop optimizing hyperparameters and look at your data when things aren't working.
- **Know When the Paradigm Has Shifted** *(Karpathy on paradigm shifts; cs231n evolution; Lex Fridman #452)* — When AlexNet happened in 2012, the old CV paradigm was over. When the Transformer happened in 2017, the LSTM paradigm was over. Recognize paradigm shifts quickly and stop investing in the obsolete paradigm.
- **Don't Keep Scaling What's Broken at Small Scale** *(A Recipe for Training Neural Networks, 2019; nanoGPT design philosophy)* — A model that doesn't work at small scale will not magically work at large scale. Diagnose and fix at small scale before scaling.
- **The 'Works on Toy Problem, Fails on Real Data' Diagnostic** *(A Recipe for Training Neural Networks, 2019)* — When a model works on the simple version but fails on the real dataset, the problem is almost always in the data, not the model. Stop debugging the model and start debugging the data pipeline.
- **Stop When You Can't Explain What the Model Has Learned** *(A Recipe for Training Neural Networks, 2019; Tesla AI Day 2021)* — A model you don't understand is a model you can't fix, improve, or trust. Do interpretability work before deploying or extending it.
- **Stop Adding Complexity Before Simplifying** *(A Recipe for Training Neural Networks, 2019)* — When a model isn't working, the first instinct is to add complexity. Usually, the correct response is to simplify — remove layers, reduce dataset size, simplify preprocessing. Complexity masks bugs; simplification reveals them.
- **The Validation Loss Test for Stopping Training** *(A Recipe for Training Neural Networks, 2019; cs231n notes)* — Train until the validation loss stops improving. Continue past this point and you're overfitting. Stop significantly before it and you're leaving performance on the table.
- **Iterate Fast, Kill Slow** *(Karpathy research approach; Zero to Hero development process)* — Run many small experiments fast, kill the ones that don't show promise immediately. Most experiment ideas are wrong. The faster you learn this and move on, the more good ideas you'll eventually test.
- **Stop Using RNNs When Transformers Work Better** *(Karpathy on Transformers; cs231n evolution; Lex Fridman #452)* — Karpathy was among the earliest serious practitioners to migrate from LSTMs to Transformers after 'Attention Is All You Need' (2017). Recognize obsolescence quickly and migrate. The switching cost is probably lower than the performance cost of staying.

---

## 2026 Overlay

### Where the alpha is
- LLM infrastructure at the systems level: llm.c and CUDA kernels — the performance-critical layer that determines inference cost
- Physical AI and autonomous systems: perception + planning + action in the real world, the hardest Software 2.0 problem
- AI-native education: teaching that leverages LLMs to create personalized, interactive learning at scale
- Interpretability and mechanistic understanding of neural networks: the field's deepest open problem, with enormous practical implications
- Open-weight models as infrastructure: the ecosystem around open models is the platform opportunity of the current era

### Auto-reject
- Pure LSTM/RNN architectures for sequence modeling — Transformers have definitively won this comparison
- Hand-crafted feature engineering pipelines in domains where end-to-end learned representations work better
- Model complexity for its own sake — the simplest model that achieves the task is almost always the right model
- Training without validation loss monitoring — flying blind
- Hyperparameter search without first understanding the data — optimizing the wrong thing

---

## Verdict logic

Run each doctrine against the candidate AI research project or engineering effort. Mark **Pass / Weak / Fail** with notes. Then:

- **Kill** — any single Fail in Layer 1 (Problem-Selection), or 3+ Fails total
- **Proceed** — zero Fails, ≤2 Weaks, ≥60% Pass coverage across scored doctrines
- **Reconsider** — anything else

The Build From Scratch test is the master competence filter: if you cannot implement the core system from scratch and match published results, your understanding is theoretical, not operational. All subsequent doctrine application assumes operational understanding.
