import json
import os

# for i in range(1,10):
#     folder_name = f"task_{i}"
#     os.makedirs(folder_name, exist_ok=True)

task = "task_9"

folder_name = task

with open(f"{folder_name}/data.json", mode='r', encoding='utf8') as json_file:
    # Write the JSON data to the file
    data = json.load(json_file)

d_array = {}
array_id = []
count = 1

"""
 {
        "image": null,
        "context": "Following location are adjacent to each other:\nHayama(lat:34.04369149960314,long-118.4462718)\nPlan Check(lat:34.043906699603156,long-118.44599299999999)\n",
        "question": "What restaurant is right by Hayama?",
        "pid": "0",
        "answer": "Plan Check",
        "location": "california",
        "category": "Geo-entity",
        "concepts": "Amenity type & Closeness",
        "prefix": "adjacent_dataset",
        "type": "type_1"
}

    "34": {
        "question": "My office is at Agargaon ICT Tower. One of my colleagues has broken his leg accidentally. I want to take him to an orthopedic hospital near me. Suggest me an orthopedic hospital near ICT tower, Agargaon, Dhaka.",
        "choices": [
            "National Institute of Traumatology and Orthopaedic Rehabilitation (NITOR)",
            " Mary Orthopedic General Hospital and Diagnosis Center",
            "Amader Hospital Ltd",
            "National Institute of Laboratory Medicine & Referral Center (NILMRC)"
        ],
        "answer": " Mary Orthopedic General Hospital and Diagnosis Center",
        "hint": "",
        "image": "",
        "skill": "Fetch context from corresponding google map api and based on the context answer the question ",
        "solution": "To find the answer, You have to choose one option from the MCQ",
        "split": "test",
        "classification": "geospatial"
    },
"""


for row in data:
    d = row
    location = d['location']
    context = d['context']
    question = d['question']
    d['question'] = f"{question} All the location are inside California. In final answer pick only one location. Context: {context}"
    d['choices'] = [d['answer']]
    d["hint"] = ""
    d["skill"] = "Fetch context from corresponding google map api and based on the context answer the question "
    d["solution"] = "To find the answer, You have to choose one option from the MCQ"
    d["split"] = "test"
    d["classification"] = d['type']
    d_array[count] = d
    array_id.append(f"{count}")
    count = count + 1

with open(f"{folder_name}/problems.json", mode='w', encoding='utf8') as json_file:
    # Write the JSON data to the file
    json.dump(d_array, json_file, ensure_ascii=False, indent=4)


pid_split = {
    "minitest": array_id
}
# Open a file for writing in write mode with UTF-8 encoding
with open(f"{folder_name}/pid_splits.json", mode='w', encoding='utf8') as json_file:
    # Write the JSON data to the file
    json.dump(pid_split, json_file, ensure_ascii=False, indent=4)
