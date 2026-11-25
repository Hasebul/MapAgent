"""MapAgent: A Hierarchical Agent for Geospatial Reasoning with Dynamic Map Tool Integration.

Findings of the Association for Computational Linguistics: EACL 2026.

The package is organised following Section 3 of the paper:

* ``mapagent.solver``      - Planner Agent (outer layer) and module execution.
* ``mapagent.modules``     - Module inventory (Table 10): Visual Place Recognizer, Map Service,
                             Sequencer, Solution Generator and Answer Generator.
* ``mapagent.map_tools``   - Map-Tool Agent (inner layer) and the four MapTools (Table 11).
* ``mapagent.prompts``     - Prompts (Appendix B).
* ``mapagent.data``        - Benchmark loaders (MapEval-API/Textual/Visual and MapQA).
* ``mapagent.scoring``     - Answer extraction and accuracy computation.
"""

__version__ = "1.0.0"
