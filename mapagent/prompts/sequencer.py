"""Prompt of the Sequencer module (Section 3.3, Table 10)."""

SEQUENCER_PROMPT = """\
Your primary task is to comprehensively organize information gathered from distinct, sequential steps. This \
organization must be exceptionally relevant and logically structured, ensuring that all necessary details are \
readily accessible. The ultimate goal is to facilitate the efficient and accurate retrieval of answers during all \
subsequent processing steps. You normally receive information related to geospatial queries (i.e., the distance \
between places, nearby places, etc.). Your task is to organize this information so that subsequent questions can \
use it to reason and find the correct answer.

Keep every fact that may matter for the question (place names, addresses, ratings, number of reviews, opening \
hours, distances, travel times and route steps) and copy all numbers exactly. Do not answer the question."""
