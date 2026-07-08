PROMPTS = {
    "Algoritmos": "Focus heavily on time/space complexity, data structures, and optimal approaches.",
    "System Design": "Focus heavily on scalability, databases, microservices, load balancing, and trade-offs.",
    "Behavioral": "Use the STAR method (Situation, Task, Action, Result) implicitly in your script, drawing from the candidate's context.",
    "Inglés": "Ensure the English is absolutely perfect, highly professional, and showcases strong communication skills. Keep it conversational.",
    "OOP": "Focus on SOLID principles, design patterns, inheritance, polymorphism, and encapsulation.",
    "SQL": "Focus on JOINs, indexing, normalization, window functions, and query optimization.",
    "General": "Provide a natural, conversational response."
}

# Derived from PROMPTS to guarantee they stay in sync.
CATEGORIES = list(PROMPTS.keys())

CLASSIFIER_PROMPT = (
    "Analyze the following interview transcription chunk and classify it into exactly "
    f"ONE of the following categories:\n{', '.join(CATEGORIES)}.\n"
    "Output ONLY the category name, nothing else."
)

