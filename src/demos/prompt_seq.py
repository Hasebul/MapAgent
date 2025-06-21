# cot
prompt_cot = """

Given the question (and the context), select the answer from the options ["A", "B", "C", "D", "E"]. You should give consice and step-by-step solutions. Finally, conclude the answer in the format of "the answer is [ANSWER]", where [ANSWER] is one from the options ["A", "B", "C", "D", "E"]. For example, "the answer is A", "the answer is B", "the answer is C", "the answer is D", or "the answer is E". If the answer is not in the options, select the most possible option.

Question: Which property do these two objects have in common?

Context: Select the better answer. Image: A pair of scissors next to a pair of scissors.

Options: (A) hard (B) bendable

Solution: An object has different properties. A property of an object can tell you how it looks, feels, tastes, or smells.\nDifferent objects can have the same properties. You can use these properties to put objects into groups. Look at each object.\nFor each object, decide if it has that property.\nA bendable object can be bent without breaking. Both objects are bendable.\nA hard object keeps its shape when you squeeze it. The rubber gloves are not hard.\nThe property that both objects have in common is bendable.\n\nTherefore, the answer is B.

Question: Select the one substance that is not a mineral.

Context: Select the better answer.

Options: (A) turtle shell is not a pure substance. It is made by a living thing (B) Celestine is a pure substance. It is a solid. (C) Hematite is not made by living things. It is a solid.

Solution: Compare the properties of each substance to the properties of minerals. Select the substance whose properties do not match those of minerals.\nA turtle shell is made by a living thing. But minerals are not made by living things.\nA turtle shell is not a pure substance. But all minerals are pure substances.\nSo, a turtle shell is not a mineral.\nCelestine is a mineral.\nHematite is a mineral.\nTherefore, the answer is A.
"""

# chameleon
prompt_chameleon = """Your primary task is to comprehensively organize information gathered from distinct, sequential 
steps. This organization must be exceptionally relevant and logically structured, ensuring that all necessary details 
are readily accessible. The ultimate goal is to facilitate the efficient and accurate retrieval of answers during all 
subsequent processing steps. You normally receive information related to geospatial queries (i.e., the distance between 
places, nearby places, etc.). Your task is to organize this information so that subsequent questions can use it to 
reason and find the correct answer."""