# The Karpathy Doctrine

> "Don't try to be a good researcher. Try to work on important, interesting problems, and understand them deeply."

**About:** A three-layer filter for doing serious AI and software work. Distilled from 'Software 2.0' (Medium, 2017), 'A Recipe for Training Neural Networks' (karpathy.github.io, 2019), 'Neural Networks: Zero to Hero' YouTube series (2022-2023), 'State of GPT' at Microsoft Build (2023), Lex Fridman #333 and #452, the nanoGPT/micrograd/minbpe/llm.c GitHub repos, and the full @karpathy Twitter/X corpus.

---
## Layer 1 — Problem-Selection Taste
*What is worth working on at all*

Karpathy's problem-selection doctrine is organized around one foundational idea: Software 2.0. The most important problems are those where neural networks replace hand-written code — where the software is learned from data rather than explicitly programmed. Within that frame, the highest-leverage work is at the infrastructure layer: the tools, methods, and mental models that allow the entire field to move faster.

### Software 2.0 — The Paradigm Shift
**Rule:** Software 1.0 is code that humans write. Software 2.0 is code (neural network weights) written by optimization over data. Every domain where Software 2.0 can replace Software 1.0 is undergoing the most important software transition in decades.

**Test:** In this domain, is the current software hand-written rule-based code that could be replaced by a learned neural model? If yes and the transition hasn't happened yet, this is a Software 2.0 opportunity. If the domain already uses learned models pervasively, the first-mover advantage is gone.

**Source:** Software 2.0, Medium, November 2017

### Work on Infrastructure That Benefits the Entire Field
**Rule:** The highest-leverage contribution makes it easier for everyone to do the important work. Tools that accelerate 1,000 researchers are worth more than research that advances one person's understanding.

**Test:** If this project succeeds, how many researchers or engineers does it directly unblock or accelerate? Infrastructure that helps 1,000 is more valuable than a result that advances 1. Require an honest estimate of the multiplier.

**Source:** nanoGPT GitHub; Lex Fridman #333; Zero to Hero series

### Build From Scratch to Understand
**Rule:** The only way to genuinely understand a complex system is to build it from scratch. Build micrograd (autograd in 25 lines), then makemore, then nanoGPT. Each level builds on the previous and you understand every line.

**Test:** Can the person implement the core system from scratch — from memory, matching published results — without referring to existing code? If not, understanding is theoretical, not operational.

**Source:** Neural Networks: Zero to Hero, 2022-2023; micrograd repo

### The Tight Feedback Loop Imperative
**Rule:** Problems where you can iterate in minutes rather than days compound learning faster. The feedback loop speed is a direct multiplier on your learning rate.

**Test:** What is the current iteration cycle time — from hypothesis to experimental result? Minutes = fast learning. Days = slow learning. Weeks = research that cannot effectively self-correct.

**Source:** A Recipe for Training Neural Networks, 2019; Zero to Hero

### Work on Problems Where Intuition Is Still Being Built
**Rule:** Mature problems have accumulated intuition. Emerging problems have none. Building intuition in a new domain is among the highest-leverage activities because your insights become the field's starting point.

**Test:** Does the current problem have an established set of heuristics and intuitions that practitioners agree on? If yes, the intuition-building opportunity is largely captured. If no — the field is still confused about basics — this is high-leverage territory.

**Source:** Karpathy talks on deep learning intuition; Lex Fridman #452

### Pick Problems Where the Simplest Implementation Teaches the Most
**Rule:** Problems that can be illuminated by a 500-line implementation are more valuable as teaching tools than those requiring 500,000 lines. The minimal implementation that demonstrates the key principle is both a research tool and an educational one.

**Test:** What is the minimum number of lines required to demonstrate the key insight of this problem? Can the core principle be implemented in under 1,000 lines? If the minimum demonstration requires a large codebase, the problem may not have been reduced to its essence.

**Source:** micrograd repo, 2020; nanoGPT repo, 2022; Zero to Hero

### The 'Can I Implement It From Scratch?' Test
**Rule:** The deepest test of understanding is implementation. Reading a paper and understanding it are different things. Implement the paper from scratch, match the results, understand every design choice.

**Test:** Take the last paper read and attempt to implement it from scratch. Did the implementation match published results? Every divergence from published results reveals a misunderstanding. Zero divergences = actual understanding.

**Source:** Zero to Hero series; nanoGPT repo; Karpathy teaching discussions

### Inspect Your Data Before Your Model
**Rule:** The most common and costly mistake in machine learning is optimizing the model when the problem is in the data. Look at your data first, always. More data of worse quality is usually worse than less data of better quality.

**Test:** Before any model changes: have 100 random training examples been manually inspected? And 100 random validation examples? If not, data inspection has been skipped and model problems may actually be data problems.

**Source:** A Recipe for Training Neural Networks, 2019; Zero to Hero

### LLMs as the New Operating System Layer
**Rule:** Large language models are becoming the new operating system layer for software applications. This architectural shift creates the same kind of platform opportunity that operating systems created in the 1980s.

**Test:** Does this product or research sit at the interface between LLM capabilities and application use cases — where the LLM is the substrate rather than the application? If yes, it is positioned at the new OS layer. If the LLM is incidental, it is not.

**Source:** State of GPT, Microsoft Build 2023; Hacker's Guide to Language Models, 2023

### The Education Multiplier
**Rule:** Teaching is among the highest-leverage activities in technology. Each person who deeply understands neural networks can produce years of compounded research impact.

**Test:** How many people has this person directly caused to deeply understand a technical concept? Deep understanding means they can implement it from scratch. Surface understanding doesn't count. A strong teaching record is a high-leverage multiplier.

**Source:** Zero to Hero series; cs231n Stanford; Lex Fridman #333

### Work on the Bottleneck, Not the Solved Part
**Rule:** Every AI system has a bottleneck whose improvement would most increase overall performance. Most researchers work on parts they find interesting, not the bottleneck. Identify the true bottleneck first (often data, not model).

**Test:** In the current AI system, which component most limits overall performance — model capacity, data quality, data volume, inference speed, or training stability? Is the current work focused on that bottleneck, or on a different (perhaps more interesting) component?

**Source:** A Recipe for Training Neural Networks, 2019; Tesla AI Day 2021

---
## Layer 2 — Approach Taste
*Given the problem, which angle to attack from*

Karpathy's approach doctrine is built around one core discipline: empirical rigor. Intuitions must be tested; results must be visualized; assumptions must be challenged. The 'Recipe for Training Neural Networks' is the canonical statement — a systematic protocol for debugging and improving neural networks that generalizes to any empirical machine learning work.

### The Recipe: Become One With the Data First
**Rule:** Before writing a single line of model code: examine your data. Understand the distribution, find the outliers, identify mislabeled examples, count the classes.

**Test:** Before any model code was written for this project, were at least 100 training examples manually inspected? Were the class distributions counted? Were outliers catalogued? If any of these were skipped, model problems may actually be data problems in disguise.

**Source:** A Recipe for Training Neural Networks, 2019

### Overfit a Single Batch First
**Rule:** Before training on the full dataset, train on a single batch of 5-10 examples until loss goes to near-zero. This verifies that your model can learn at all.

**Test:** Can the model overfit a 5-example batch to near-zero loss? If not, there is a bug in the model, the loss function, or the optimizer that must be fixed before any further experimentation.

**Source:** A Recipe for Training Neural Networks, 2019

### Visualize Everything
**Rule:** Loss curves, activation distributions, gradient magnitudes, attention patterns, failure cases — you cannot debug what you cannot see. Instrument your training pipeline to make every important quantity observable.

**Test:** List the quantities currently being visualized during training. Are loss curves, gradient norms, activation distributions, and sample outputs all being monitored? Any unmonitored quantity is a potential undetected problem.

**Source:** A Recipe for Training Neural Networks, 2019; Zero to Hero

### The Baby Model Protocol
**Rule:** Before training the full model, train a minimal version. Debug on the small model first. The small model trains faster, costs less, and reveals the same class of bugs.

**Test:** Has the current model been validated at minimal scale — 10% of the parameters, 10% of the data — before scaling to full size? Bugs found at small scale are far cheaper than bugs found at full scale.

**Source:** A Recipe for Training Neural Networks, 2019; nanoGPT design philosophy

### The Learning Rate Is the Most Important Hyperparameter
**Rule:** Too high = loss explodes; too low = too slow to converge; wrong schedule = premature convergence. Always use a learning rate finder before committing to a long training run.

**Test:** Before the current long training run, was a learning rate sweep conducted? The optimal learning rate produces the steepest early loss decline without explosion. Committing to a long run without a learning rate sweep is speculation.

**Source:** A Recipe for Training Neural Networks, 2019

### Use the Loss Curve as the Primary Diagnostic
**Rule:** Loss not decreasing: learning rate too low or data problem. Loss oscillating: learning rate too high. Loss plateauing: model or dataset too small. Read the loss curve before changing anything.

**Test:** For the current training run, state the loss curve shape and the diagnosis it implies. If the diagnosis is "I'm not sure," the loss curve is not being used as a diagnostic — it is being ignored.

**Source:** A Recipe for Training Neural Networks, 2019

### The Dead Neuron Diagnostic
**Rule:** In ReLU networks, monitor the fraction of neurons with non-zero activations. If more than 30% are dead after initialization, adjust your initialization or learning rate.

**Test:** What fraction of ReLU neurons are dead (zero activation on all training examples) after initialization? Above 30% dead = initialization or learning rate problem that must be fixed before any other optimization.

**Source:** A Recipe for Training Neural Networks, 2019; cs231n

### Inspect Failures, Not Just Successes
**Rule:** Sample from the worst-performing examples and look at them manually. The pattern in failures tells you what the model is missing, what the data is missing, or what the problem formulation is wrong about.

**Test:** From the last evaluation, have the 20 worst-performing examples been manually inspected? What pattern do they share? If no failure analysis has been done, the most informative signal is being ignored.

**Source:** A Recipe for Training Neural Networks, 2019; Tesla AI Day 2021

### The Gradient Flow Audit
**Rule:** Monitor gradient norms layer-by-layer during training. If early layer gradients are 100x smaller than late layer gradients, you have gradient vanishing.

**Test:** Plot the gradient norm per layer for the last training run. Is the gradient norm roughly uniform across layers, or does it decay significantly toward early layers? Gradient decay >10x from last to first layer indicates a gradient flow problem.

**Source:** A Recipe for Training Neural Networks, 2019; cs231n

### The Numerical Stability Check
**Rule:** Add numerical stability checks throughout your code: assert that loss is finite, that gradients are finite, that weights are finite. Catch instability early before it corrupts a long training run.

**Test:** Does the training code include assertions that loss, gradients, and weights are finite at each step? If a long training run produced NaN values only at hour 8, the stability checks were absent.

**Source:** A Recipe for Training Neural Networks, 2019

### Write Minimal, Readable Code
**Rule:** No abstractions beyond what the problem requires, explicit variable names, clear data flow. Complexity is the enemy of understanding. Never add an abstraction before you've used the primitive 3 times.

**Test:** Can a competent engineer who has never seen this codebase understand what each function does from its name and a 30-second read? If not, the code has exceeded the minimal-abstraction standard.

**Source:** nanoGPT repo; micrograd repo; llm.c repo; Karpathy coding philosophy

### Read Papers AND Implement Them
**Rule:** Reading a paper produces surface-level understanding. Implementing the paper — getting it to work, matching reported results, debugging the gaps — produces deep understanding.

**Test:** For the last 5 papers read, how many were implemented from scratch? If zero, reading is producing surface-level familiarity rather than deep understanding.

**Source:** Karpathy's approach to learning; Zero to Hero philosophy

### Teach to Learn
**Rule:** The act of explaining a concept clearly reveals gaps in your own understanding. The Zero to Hero series is a discipline of verification: if you can explain it to a non-expert, you truly understand it.

**Test:** Can the person explain the current technical concept to a smart non-expert in 15 minutes with no jargon? Attempt it. Every failure to explain is a gap in understanding, not a gap in the listener.

**Source:** Zero to Hero series philosophy; Karpathy on teaching as learning

### The Baseline Before the Innovation
**Rule:** Before proposing a novel approach, establish a strong baseline with the simplest possible method. Many 'improvements' disappear when compared against a properly tuned simple method.

**Test:** What is the best result from the simplest possible method (linear model, simple MLP, off-the-shelf pretrained model)? Does the proposed innovation outperform this properly-tuned baseline? Many "novel" approaches fail this test.

**Source:** A Recipe for Training Neural Networks, 2019; ML research methodology

### Run Experiments in Public
**Rule:** Publishing code, findings, and experiments publicly — before they're polished — accelerates the field and builds your reputation. The internet will improve your rough work faster than you will alone.

**Test:** Is the current codebase publicly accessible? Has any result been shared publicly before it was "fully ready"? Waiting for perfection before publishing is the anti-pattern; early public release gets earlier external feedback.

**Source:** Zero to Hero series; nanoGPT and micrograd release philosophy

### The Simplest Working Architecture First
**Rule:** Start with the simplest architecture that could possibly work. Add complexity only when you have evidence that simpler isn't sufficient.

**Test:** What is the simplest architecture that could achieve the goal? Has that been tried first and demonstrated to be insufficient before adding complexity? If the first model tried was complex, simplest-first was skipped.

**Source:** A Recipe for Training Neural Networks, 2019; nanoGPT design

### Work With the Best Environment
**Rule:** GPU availability, fast data loading, efficient logging, and reproducible experiments are the infrastructure that makes research fast. Fix the bottleneck before doing more experiments with the bottleneck in place.

**Test:** What is the current bottleneck in the research environment — GPU memory, data loading speed, experiment tracking, reproducibility? Is that bottleneck being fixed before more experiments are run through it?

**Source:** Zero to Hero series; cs231n notes

### Work in Public With the Best
**Rule:** The fastest way to improve is to work alongside the best researchers in the world. The intellectual density of your environment is the primary determinant of growth rate.

**Test:** What is the intellectual density of the current environment? Are the people within daily interaction range among the best in the relevant field? If not, remote collaboration with or public visibility to the best is a partial substitute.

**Source:** Lex Fridman #333; Lex Fridman #452

### The Right Size of Problem Requires Iteration
**Rule:** Run many small experiments fast, kill the ones that don't show promise immediately, and invest deeply only in the promising directions. Most experiment ideas are wrong.

**Test:** How many small experiments were run last week? And how many were killed after showing no promise? High kill rate combined with high experiment rate is the healthy pattern. Low kill rate means promising-looking experiments aren't being culled fast enough.

**Source:** Karpathy research approach; Zero to Hero development process

---
## Layer 3 — Stopping Taste
*When to abandon, when to push, when "done enough"*

Karpathy's stopping doctrine is empirical: stop when the data says stop, not when intuition says stop. Loss curves plateau? Stop and diagnose before continuing. The paradigm has shifted? Stop investing in the obsolete one.

### Stop When Loss Plateaus — Diagnose Before Continuing
**Rule:** A loss plateau is information: the model has learned everything it can from the current data with the current architecture. Diagnose (capacity? data? optimizer?) before continuing.

**Test:** Has the validation loss failed to improve for N epochs? (N = typically 10-20% of total training budget.) If yes, diagnose the cause before adding more compute. More training on a plateau wastes resources and teaches nothing.

**Source:** A Recipe for Training Neural Networks, 2019

### Stop Optimizing Hyperparameters Before Understanding Data
**Rule:** Hyperparameter tuning on a bad dataset produces a model that is optimally fit to the wrong problem. Stop optimizing hyperparameters and look at your data when things aren't working.

**Test:** When results are poor, what is the first action taken: inspect the data or tune hyperparameters? Hyperparameter tuning before data inspection is the wrong order — it optimizes the wrong thing faster.

**Source:** A Recipe for Training Neural Networks, 2019

### Know When the Paradigm Has Shifted
**Rule:** When AlexNet happened in 2012, the old CV paradigm was over. When the Transformer happened in 2017, the LSTM paradigm was over. Recognize paradigm shifts quickly and stop investing in the obsolete paradigm.

**Test:** For the current research investment, is there evidence that a new approach has definitively outperformed the current paradigm on standard benchmarks across multiple domains? If yes, the paradigm has shifted and continuing in the old paradigm is a losing bet.

**Source:** Karpathy on paradigm shifts; cs231n evolution; Lex Fridman #452

### Don't Keep Scaling What's Broken at Small Scale
**Rule:** A model that doesn't work at small scale will not magically work at large scale. Diagnose and fix at small scale before scaling.

**Test:** Does the model work correctly on a 1% scale version (fewer parameters, fewer data, fewer epochs)? If not, the fundamental issue must be diagnosed and fixed before spending the compute budget on a full-scale run.

**Source:** A Recipe for Training Neural Networks, 2019; nanoGPT design philosophy

### The 'Works on Toy Problem, Fails on Real Data' Diagnostic
**Rule:** When a model works on the simple version but fails on the real dataset, the problem is almost always in the data, not the model. Stop debugging the model and start debugging the data pipeline.

**Test:** Test on the simplest possible version of the problem — synthetic data, small clean subset. If it works there but fails on real data, the data pipeline has a bug. Model debugging before data debugging is the wrong order.

**Source:** A Recipe for Training Neural Networks, 2019

### Stop When You Can't Explain What the Model Has Learned
**Rule:** A model you don't understand is a model you can't fix, improve, or trust. Do interpretability work before deploying or extending it.

**Test:** Can the team explain what features the model is using to make its most important decisions? If the model is a black box and no interpretability work has been done, deploying it is irresponsible and extending it is building on sand.

**Source:** A Recipe for Training Neural Networks, 2019; Tesla AI Day 2021

### Stop Adding Complexity Before Simplifying
**Rule:** When a model isn't working, the first instinct is to add complexity. Usually, the correct response is to simplify — remove layers, reduce dataset size, simplify preprocessing. Complexity masks bugs; simplification reveals them.

**Test:** When the model fails to train, is the first response to add layers/data/augmentation, or to simplify? Simplification should always be tried first. Complexity added to fix a broken simple model usually adds complexity without fixing the bug.

**Source:** A Recipe for Training Neural Networks, 2019

### The Validation Loss Test for Stopping Training
**Rule:** Train until the validation loss stops improving. Continue past this point and you're overfitting. Stop significantly before it and you're leaving performance on the table.

**Test:** Plot training loss and validation loss on the same graph. Where does validation loss reach its minimum? Stop training at or near that point. Is the current model trained past that point (overfitting) or well before it (undertrained)?

**Source:** A Recipe for Training Neural Networks, 2019; cs231n notes

### Iterate Fast, Kill Slow
**Rule:** Run many small experiments fast, kill the ones that don't show promise immediately. Most experiment ideas are wrong. The faster you learn this and move on, the more good ideas you'll eventually test.

**Test:** What is the ratio of experiments killed to experiments continued? If every experiment that was started is still running, the kill rate is zero — which means bad ideas are not being culled. A healthy kill rate is >50% of experiments in the first 20% of planned runtime.

**Source:** Karpathy research approach; Zero to Hero development process

### Stop Using RNNs When Transformers Work Better
**Rule:** Karpathy was among the earliest serious practitioners to migrate from LSTMs to Transformers after 'Attention Is All You Need' (2017). Recognize obsolescence quickly and migrate.

**Test:** For the current sequence modeling problem, has a Transformer baseline been run and compared against the current approach? If the Transformer outperforms and is being avoided for non-technical reasons (familiarity, existing infrastructure), the migration is overdue.

**Source:** Karpathy on Transformers; cs231n evolution; Lex Fridman #452

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
