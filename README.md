## Experimental Branch

## How it Works

Operates using an "Agentic Refinement Loop" powered by dual-LLMs, followed by formal verification:

1. **Extraction**: The system parses the target Python source code using `libcst` to extract any natural language claims tagged with `# claim:` along with their corresponding function signatures.
2. **Agentic Refinement Loop (Dual-LLM)**:
   - **Drafting**: A Code-Model generates a Python assertion representing the natural language claim.
   - **Back-translation**: The generated assertion is translated back into natural language by the Code-Model.
   - **Critical Analysis**: A Reasoning-Model (Critic) compares the back-translated claim with the original claim to ensure semantic equivalence. 
   - *This loop repeats up to a maximum number of retries (default 3) until the Critic confirms a semantic match.*
3. **Symbolic Preparation**: Once a logically sound assertion is generated, Doc Check instruments the target function with CrossHair-compatible pre/post conditions.
4. **Formal Verification**: `crosshair-tool` runs symbolic execution on the instrumented code to formally prove or disprove the claim across all possible inputs.

## Setup & Installation

Ensure you have Python installed, and then install the required dependencies:

```bash
pip install -r requirements.txt
```

**Note**: The system relies on local LLMs powered by the `ollama` package. Make sure you have Ollama installed and running with the appropriate Code and Reasoning models available (e.g., Qwen and DeepSeek, as defined in your agent configurations).

## Usage

1. **Annotate your code**: Add `# claim: <your natural language claim>` directly above the function you wish to verify.
   You can optionally add `# precondition: <python condition>` on the line below the claim. **This is highly recommended** to constrain the inputs and prevent the symbolic execution engine from generating trivial or irrelevant edge cases (like testing an empty list on a function that assumes populated data).

   Example (`data/targets/test_code.py`):
   ```python
   from typing import List

   # claim: the returned value is always greater than or equal to every element in the input list
   # precondition: len(numbers) > 0
   def find_maximum(numbers: List[int]) -> int:
       if not numbers:
           return 0
       max_val = numbers[0]
       for n in numbers:
           if n > max_val:
               max_val = n
       return max_val
   ```

2. **Run Doc Check**: Point the main script to your target file. By default, it runs against `data/targets/test_code.py` in the project.

   ```bash
   python main.py
   ```

3. **Review Results**: Doc Check will output the progress of the Agentic Refinement Loop and finally present a crosshair symbolic execution verdict (`[OK]` if the claim holds true, or a counterexample if it fails) for each analyzed claim.
