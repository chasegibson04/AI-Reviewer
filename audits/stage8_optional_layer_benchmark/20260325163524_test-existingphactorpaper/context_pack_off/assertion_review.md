# Assertion Review

## CLAIM-009
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: KEYWORDS: _large language model, high-throughput experimentation, ChatGPT, reaction optimization, literature mining_

## CLAIM-011
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Chemical synthesis is a primary bottleneck in drug development.

## CLAIM-012
- section: abstract
- type: abstract_claim
- priority: high
- status: citation_exists_but_support_not_verified
- claim: High-throughput experimentation (HTE) is a widely practiced method for the discovery and optimization of reaction conditions in medicinal chemistry campaigns.[1][−][5] Chemists typically design reaction arrays based on conditions found in the literature using search tools such as Google, SciFinder, or Reaxys.
- linked_references: 2
- support_sources: science.1259203.pdf (0.14), d1sc06932b.pdf (0.0962), Predicting_reaction_conditions_from_limited_data_through_active_transfer_learnin.pdf (0.0962)

## CLAIM-013
- section: abstract
- type: abstract_claim
- priority: high
- status: citation_exists_but_support_not_verified
- claim: The automated generation of reaction arrays to optimize or discover a coupling reaction between two substrates is a contemporary problem.[6][−][12] Recently, generative transformers, a form of artificial intelligence (AI), have emerged as interactive language models that can interpret and answer scientific questions via verbal human input.[13][,][14] Herein, we demonstrate how the general-purpose language model ChatGPT can be utilized to generate initial-guess reaction array designs for specific substrate pairs.
- linked_references: 4

## CLAIM-014
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: The output can be directly translated into input files for the HTE management software phactor.[15] We showcase several case studies of using ChatGPT to aid in designing reaction arrays for phactor, specifically for transformations that are most commonly used in pharmaceutical chemistry.[16] With phactor, we execute the arrays designed by ChatGPT experimentally leading to viable first-pass reaction conditions from simple prompts that are easy to devise by non-expert users.
- linked_references: 2

## CLAIM-016
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: To test the effectiveness of reaction arrays designed by ChatGPT, a workflow to automatically generate reagent proposals and execute reaction arrays for popular reactions was developed.

## CLAIM-017
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: A typical workflow can be summarized in three steps (Figure 1):

## CLAIM-018
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: - First, we should have ChatGPT generate reaction array designs for specific substrates based on simple text prompts.

## CLAIM-019
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: - Then, we should translate the output from ChatGPT into an input file for the HTE management software

## CLAIM-023
- section: abstract
- type: abstract_claim
- priority: high
- status: cited_support_plausible
- claim: Verbal input is given by a human to have ChatGPT generate a reaction array design for a particular coupling and substrate pair.
- support_sources: science.aac6153.pdf (0.0952)

## CLAIM-024
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The output can be fed directly into phactor, creating an assay recipe to be executed robotically or manually.

## CLAIM-027
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: - Finally, we should use phactor to create stock solutions and distribute the chemicals into the reaction array, manually or robotically, and then analyze its results.

## CLAIM-028
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: ChatGPT can be interrogated during the design step to elaborate on experimental details or reasonings and was asked to clarify experimental details at times.

## CLAIM-029
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: Each product was scaled up using the best conditions identified for its respective reaction array and isolated.

## CLAIM-030
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: We note that all screen designs in this work were derived from GPT-3 model responses provided through the ChatGPT web interface accessed on February 20th, 2023.

## CLAIM-031
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: We also note that the model may provide variable responses over time, which is expected based on the evolution of the large language model and its training data.

## CLAIM-045
- section: abstract
- type: abstract_claim
- priority: high
- status: citation_exists_but_support_not_verified
- claim: ChatGPT is a newly released general-purpose AI language model developed by OpenAI.[17] It serves as a conversational model where the user can ask a series of questions and receive text answers based on the context of the conversation.
- linked_references: 1

## CLAIM-046
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: While not directly a model for chemistry, ChatGPT has been trained on a large corpus of scientific literature.

## CLAIM-047
- section: abstract
- type: abstract_claim
- priority: high
- status: cited_support_plausible
- claim: As such, in its own words, ChatGPT has “knowledge of basic chemistry concepts, such as the periodic table, chemical reactions, acids and bases, and thermodynamics.
- support_sources: d1sc06932b.pdf (0.0976), Predicting_reaction_conditions_from_limited_data_through_active_transfer_learnin.pdf (0.0976)

## CLAIM-048
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: It can also provide information on more advanced topics, such as organic chemistry, biochemistry, and physical chemistry”.

## CLAIM-049
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: We demonstrate how ChatGPT can be asked to generate reaction arrays of viable reagents and catalysts for common reaction classes for specific substrates.

## CLAIM-050
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: For each class of reactions (amide, Suzuki, and Buchwald− Hartwig couplings), we ask ChatGPT to develop an experimental design for various pairs of substrates.

## CLAIM-051
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: While we hypothesize that the model is exercising little, if any, physical and chemical intuition in its designs, its ability to select popular reagents and catalysts associated with reaction-type keywords leads to viable and interesting proposals for array recipes.

## CLAIM-052
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Critically, the merger with phactor exploits the strength of ChatGPT to propose several plausible answers and then sample them systematically using HTE as opposed to relying on a single “correct” answer.

## CLAIM-053
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: Ultimately, this merger of ChatGPT and phactor led to successful reaction conditions in every case interrogated.

## CLAIM-054
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: **Amide Coupling.** In the first conversation, we requested the generation of a reaction array to optimize an amide coupling between 2-methylbenzoic acid (1) and _p_ -toluidine (2) to form amide 3 (Figure 2).

## CLAIM-057
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Amide coupling between 1 and 2 ChatGPT was asked to optimize.

## CLAIM-058
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The reagent classes are specified in the prompt, but the specific species are generated by ChatGPT.

## CLAIM-059
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: DOIs have been omitted from the shown response as the DOI and citation references did not match the titles.

## CLAIM-060
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: Furthermore, many of the references are, to the best of our knowledge, not real.

## CLAIM-061
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: This is because ChatGPT is a language model rather than a knowledge model and has been reported to hallucinate citations.

## CLAIM-064
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: We emphasize that it is not advised to ask the model for archival data such as DOIs or direct citations at this time.

## CLAIM-066
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The experimental execution of this reaction array precisely followed the suggestions from ChatGPT with resultant reaction metadata such as concentrations, volumes, and well locations designed by phactor (Figure 3).

## CLAIM-070
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Executed reaction array and UPLC assay results of the screen designed by ChatGPT to perform the amide coupling between 1 and 2.

## CLAIM-071
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The top-performing reaction condition was repeated on a 0.2 mmol scale to afford 3 in a 94% isolated yield.

## CLAIM-072
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: (A) Best-performing reaction selected from the reaction array and isolated yield of product.
- support_sources: science.aac6153.pdf (0.1143)

## CLAIM-073
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Color bars adjacent to reagents correspond to compound color mapping generated on phactor for reaction array visualization.

## CLAIM-074
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: (B) Reaction array design and results as displayed on phactor.

## CLAIM-075
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Assay yields were calculated through the calibration curve equation derived from the isolated product over internal standard integrations.

## CLAIM-076
- section: abstract
- type: abstract_claim
- priority: high
- status: cited_support_plausible
- claim: array produced hits with a moderate assay yield, while reactions using 1-ethyl-3-(3-dimethylaminopropyl)carbodiimide (EDC) as a coupling agent failed entirely.
- support_sources: science.aac6153.pdf (0.093)

## CLAIM-077
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: Well D5, the best hit using benzotriazol-1-yloxytripyrrolidinophosphonium hexafluorophosphate (PyBOP) and _N_ , _N_ -diisopropylethylamine (DIPEA) with (4-dimethylaminopyridine) DMAP in dichloromethane (DCM), was scaled up and resulted in a 94% isolated yield of product 3.

## CLAIM-078
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: **Amide Coupling on Complex Molecule Sitagliptin.** Next, we explored how the conversation can be continued with a more complex substrate for the amide coupling.

## CLAIM-079
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: In the same dialog, we asked ChatGPT to refer to the previous question but to instead optimize the amide coupling between sitagliptin (4) and carboxylic acid 2 to form amide 5 (Figure 4).

## CLAIM-082
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Amide coupling between 4 and 1 ChatGPT was asked to optimize.

## CLAIM-083
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The resultant design is different from that with the original simpler substrates.

## CLAIM-084
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Again, the reaction array generated by ChatGPT was executed using the recipe designed by phactor (Figure 5).

## CLAIM-085
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: Seemingly, the results of this array performed better than the original amide coupling, with only 3 failed hits, but with lower overall yields.

## CLAIM-086
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: The best hit was well A6, which produced 5 in a 62% yield when using (7-azabenzotriazol-1-yloxy)tripyrrolidinophosphonium hexafluorophosphate (PyAOP), triazabicyclodecene (TBD), and 1-hydroxy-7-azabenzotriazole (HOAt) in dimethylformamide (DMF).

## CLAIM-097
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Results of the amide coupling to produce 5 designed by ChatGPT and phactor when executed experimentally.

## CLAIM-098
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The topperforming reaction condition was repeated on a 0.4 mmol scale to afford 5 in a 62% isolated yield.

## CLAIM-099
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: (A) Best-performing reaction selected from the reaction array and isolated yield of product.
- support_sources: science.aac6153.pdf (0.1143)

## CLAIM-100
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Color bars adjacent to reagents correspond to compound color mapping generated on phactor for reaction array visualization.

## CLAIM-101
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: (B) Reaction array design and results as displayed on phactor.

## CLAIM-102
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Assay yields were calculated through the calibration curve equation derived from the isolated product over internal standard integrations.

## CLAIM-103
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: **Suzuki Coupling.** We then attempted to optimize a Suzuki coupling reaction.

## CLAIM-104
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: A new chat was initiated with ChatGPT to propose new inputs for phactor.

## CLAIM-105
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Here, we asked for an optimized reaction array to form biaryl 8 from the Suzuki coupling between boronate 6 and chloride 7 (Figure 6).

## CLAIM-109
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: Suzuki coupling between 6 and 7 ChatGPT was asked to optimize.

## CLAIM-111
- section: abstract
- type: abstract_claim
- priority: high
- status: internally_supported
- claim: The model performed well at pulling ligands and catalysts from the literature corpus, as well as generating additional parameters needed for the assay.

## CLAIM-112
- section: abstract
- type: abstract_claim
- priority: high
- status: likely_overstated
- claim: These probabilistic proposals for ligands and reagents are the perfect input for phactor, which then enables systematic testing of all combinations.
