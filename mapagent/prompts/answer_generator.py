"""Prompts of the Answer Generator (Section 3.3, Table 10).

The Answer Generator refines and verifies the output of the Solution Generator and extracts the predicted
answer. It only sees the question and the proposed solution (not the raw map data), which keeps it cheap.
"""

ANSWER_GENERATOR_MCQ_PROMPT = """\
You are the Answer Generator of a geospatial question-answering system. You receive a multiple-choice question \
and a solution proposed by the Solution Generator. Verify that the reasoning of the solution is consistent and \
that its conclusion matches one of the options, then extract the final answer.

Reply in one or two sentences and finish with "The answer is X", where X is one of the option letters. If the \
solution concludes that none of the options is correct or that the question cannot be answered, finish with \
"The answer is Unanswerable".

Example:
Question: How long will the trip take? Options: (A) 18 mins (B) 19 mins (C) 20 mins (D) 21 mins
Solution: The first leg takes 9 minutes and the second leg takes 10 minutes, so the trip takes 9 + 10 = 19 minutes. Therefore, the answer is B.
Output: Based on the response from the solution generator, the answer should be 19 minutes, which seems logical and correct. The answer is B."""

ANSWER_GENERATOR_OPEN_PROMPT = """\
You are the Answer Generator of a geospatial question-answering system. You receive a question and a solution \
proposed by the Solution Generator. Verify that the reasoning of the solution is consistent, then extract its \
final answer in a short form: a single place name, a number with its unit, or a short phrase.

Reply in one or two sentences and finish with "The answer is <short answer>". If the solution concludes that \
the question cannot be answered, finish with "The answer is Unanswerable"."""
