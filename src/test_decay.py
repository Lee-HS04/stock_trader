import subprocess
import json
import time

def get_memory_score():
    with open("short_term_memory.json", "r") as f:
        data = json.load(f)
        return data[-1]['importance_score']

print("--- Starting TITAN Decay Test ---")

# Step 1: Inject an initial memory with high importance
subprocess.run(["python", "memory_gate.py", "--ticker", "TEST", "--price", "110", "--ma", "100"])
initial_score = get_memory_score()
print(f"Initial Importance Score: {initial_score}")

# Step 2: Run the script 3 more times with 'flat' data to trigger the decay loop
for i in range(1, 4):
    subprocess.run(["python", "memory_gate.py", "--ticker", "TEST", "--price", "100", "--ma", "100"])
    current_score = get_memory_score()
    print(f"Run {i} - Importance Score after 10% decay: {current_score}")

# Step 3: Validation
if current_score < initial_score:
    print("\nSUCCESS: The Forgetting Gate is working. Memory is decaying as intended.")
else:
    print("\nFAILURE: Importance score did not decrease.")