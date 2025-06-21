
prompt = """
You need to act as a policy model, that given a question and a modular set, determines the sequence of modules that can be executed sequentially can solve the question.

The modules are defined as follows:

- Query_Generator: This module generates a search engine query for the given question. Normally, we consider using "Query_Generator" when the question involves domain-specific knowledge.

- Bing_Search: This module searches the web for relevant information to the question. Normally, we consider using "Bing_Search" when the question involves domain-specific knowledge.

- google_maps: This module find location information from google maps. Normally we consider using "google_maps" when the question involves location type questions

- visual_place_recognizer: This module determines the center location of the image and then estimates the image's boundaries from that central point.

- sequencer: This module organizes the information fetched by the Google Maps module in a logical manner, making reasoning easier and allowing the LLM to figure out the correct answer.

- Image_Search: This module generates a caption for the given image. Normally, we consider using "Image_Captioner" when the question involves the semantic understanding of the image, and the "has_image" field in the metadata is True.

- Text_Detector: This module detects the text in the given image. Normally, we consider using "Text_Detector" when the question involves the unfolding of the text in the image, e.g., diagram, chart, table, map, etc., and the "has_image" field in the metadata is True.

- Knowledge_Retrieval: This module retrieves background knowledge as the hint for the given question. Normally, we consider using "Knowledge_Retrieval" when the background knowledge is helpful to guide the solution.

- Solution_Generator: This module generates a detailed solution to the question based on the information provided. Normally, "Solution_Generator" will incorporate the information from "Query_Generator", "Bing_Search", "Image_Captioner", "Text_Detector", and "Knowledge_Retrieval".

- Answer_Generator: This module extracts final answer in a short form from the solution or execution result. This module normally is the last module in the prediction pipeline.

Below are some examples that map the problem to the modules.

Question: Find the nearest hospital from Green Delta AIMS Tower, Mohakhali?

Options: (A) MOHAKHALI CANCER AND GENERAL HOSPITAL (B) Square Hospitals Limited (c) United Hospital Limited (d) Millennium Specialized Hospital

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: Find the nearest police station from Bashundhara Residential Area, Dhaka?

Options: (A) Bashundhara Police Station (B) Gulshan Police Station (C) Banani Police Station (D) Uttara Police Station

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: Find the nearest supermarket from Baridhara Diplomatic Zone, Dhaka?

Options: (A) Meena Bazar (B) Agora Super Shop (C) Shwapno (D) Unimart

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: Find the nearest gas station from Uttara, Dhaka?

Options: (A) Padma Oil Company Limited (B) Eastern Refinery Limited (C) Meghna Petroleum Limited (D) Petromax CNG Ltd.

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: What's the fastest driving route from D03 Flame Tree Ridge to Aster Cedars Hospital, Jebel Ali?

Options: (A) Via Hessa St/D61 (B) Via Garn Al Sabkha St/D59 (C) Via D57 (D) Via Al Asayel St/D72

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: I am driving from The Ritz Carlton to the Bellagio Hotel in Las Vegas. What is the quickest route to take?

Options: (A) Turn left onto S Las Vegas Blvd (B) Turn right onto E Flamingo Rd (C) Turn right onto Paradise Rd (D) Turn left onto Sands Ave

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: What is the best walking route from Times Square to the Empire State Building?

Options: (A) Turn right onto 7th Ave (B) Turn left onto Broadway (C) Turn right onto 34th St (D) Turn left onto 5th Ave

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: I live at Indira Road. If I leave home at 8 pm, will I be able to reach sultan's dine and take dinner (which takes approximately 1 hour) before it closes? I will use my car.

Options: (A) Yes (B) NO

Modules: ["google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: How many hiking points are there?

Options: (A) Two (B) Three (C) One (D) Four

Modules: ["visual_place_recognizer", "google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: How many restaurants or cafe are on the road Cekik - Seririt?

Options: (A) Two (B) Three (C) One (D) Four

Modules: ["visual_place_recognizer", "google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]

Question: Could you please determine the total number of universities?

Options: (A) Seven (B) Nine (C) Eight (D) Ten

Modules: ["visual_place_recognizer", "google_maps", "sequencer", "Solution_Generator", "Answer_Generator"]
"""