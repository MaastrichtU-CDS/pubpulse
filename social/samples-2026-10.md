# LinkedIn draft samples — verified journal papers, 20 Sep – 21 Oct 2026

Written from the abstracts only, in the format the weekly pipeline will produce. Preprints are excluded.
`[check]` marks a claim to verify against the full paper before posting. Nothing is posted automatically:
a person copies, edits and posts.

---

## 1. Construction of personal health knowledge graphs for clinical data harmonization in breast cancer
npj Breast Cancer, 12 Oct 2026 · group authors: Cecile Wolfs, Andre Dekker, Petros Kalendralis (first author Wenjie Liang)

**LinkedIn post**

Breast cancer records from a hospital can be turned into a validated, machine-readable "personal health knowledge graph", and registries built that way in three hospitals were interoperable.

With patient consent, breast cancer data were extracted from the hospital systems and mapped to a reference ontology by a virtual assistant that combines classic rules with AI support. Every patient graph was checked with a SHACL validator before use, and one SPARQL query over the validated graphs produced a local breast cancer registry. The prototype runs in Maastricht and in two hospitals abroad [check: which countries].

Why it matters: keeping clinical registries up to date is slow manual work. A validated graph per patient makes secondary use across hospitals possible without re-entering data.

Limitation: this is a first prototype in three hospitals; how well the AI-supported mapping holds up at scale is not yet shown [check].

Paper: https://doi.org/10.1038/s41523-026-01068-y
Full text: open access

**Short version**
A virtual assistant turns breast cancer records into validated personal health knowledge graphs. Registries built this way in three hospitals were interoperable. https://doi.org/10.1038/s41523-026-01068-y

---

## 2. AI Model Reporting Standards in Health Care: Systematic Review and Consolidation
JMIR AI, 9 Oct 2026 · group authors: Simone Mingels, Andre Dekker, Johan van Soest (first authors Ekaterina Akhmad, Daniël Slob)

**LinkedIn post**

Reporting standards for AI models in health care exist in numbers, but as plain text, so the information they ask for cannot be read by machines. This systematic review consolidates them.

Following PRISMA 2020, the team searched Scopus, Web of Science, MEDLINE, Embase, IEEE Xplore and the ACM Digital Library for standards published between 2016 and April 2026, covering structured data, images and text. Two reviewers screened independently with a third for consensus, and the included standards were analysed for the lifecycle stages they describe. [check: number of standards included and the main consolidation result; the stored abstract is cut off before the results]

Why it matters: if the items of these standards were machine-readable, model documentation could be validated and compared automatically instead of by hand.

Limitation: only open-access, English, peer-reviewed standards were included [check].

Paper: https://doi.org/10.2196/92329
Full text: open access

**Short version**
A systematic review consolidates AI model reporting standards in health care (2016 to 2026) and makes the case for machine-readable reporting. https://doi.org/10.2196/92329

---

## 3. Navigating the privacy-accuracy tradeoff: federated survival analysis with binning and differential privacy
Frontiers in Applied Mathematics and Statistics, 7 Oct 2026 · group authors: Johan van Soest, Andre Dekker, Leonard Wee (first author Varsha Gouthamchand)

**LinkedIn post**

Two privacy techniques on top of federated survival analysis kept hazard ratios almost unchanged while hiding individual time-to-event data.

In the Personal Health Train set-up, hospitals share model gradients instead of patient data, but some attacks on that infrastructure can still leak sensitive information. The study tested two protections for federated Cox proportional hazards models: grouping event times into bins so no individual time point is exposed, and local differential privacy, which adds noise to the gradients before they leave the hospital.

Both approaches reduced the privacy risk with only small variations in hazard ratios and cumulative baseline hazard curves.

Why it matters: multi-hospital survival studies can be run with a smaller re-identification risk, using methods that fit an existing federated infrastructure.

Limitation: the abstract reports the accuracy effect qualitatively; the size of the privacy gain depends on the attack model considered [check].

Paper: https://doi.org/10.3389/fams.2026.1917462
Full text: open access

**Short version**
Binning event times or adding differential privacy to federated Cox models reduces re-identification risk with only small changes to hazard ratios. https://doi.org/10.3389/fams.2026.1917462

---

## 4. The impact of intratumor heterogeneity on outcome and resistance to therapy in primary breast cancer: a systematic review
Medical Oncology, 3 Oct 2026 · group authors: Andre Dekker, Leonard Wee (first author Aria Dianati)

**LinkedIn post**

Across twelve studies, high or increasing intratumor heterogeneity in primary breast cancer was associated with reduced sensitivity to chemotherapy.

The review followed PRISMA and searched MEDLINE, Web of Science and Scopus through June 2026. The twelve included studies covered triple-negative, HER2-positive and mixed cohorts, and assessed heterogeneity with genomic, transcriptomic, radiomic or immunologic methods. Proposed mechanisms behind the resistance include clonal selection, transcriptional plasticity, immune exclusion and phenotypic drift. Radiomic and MRI-derived features added predictive value beyond molecular classifiers, and combined radiomic-genomic models performed better than either alone [check: in how many of the studies].

Why it matters: heterogeneity is recognised as a core feature of breast cancer biology but is not yet used in routine care; imaging-based measures could make it usable without extra biopsies.

Limitation: twelve heterogeneous studies with different assessment methods, so no pooled effect size.

Paper: https://doi.org/10.1007/s12032-026-03426-z
Full text: open access

**Short version**
Systematic review of 12 studies: higher intratumor heterogeneity in primary breast cancer goes with lower chemotherapy sensitivity; imaging-based measures add predictive value. https://doi.org/10.1007/s12032-026-03426-z

---

## 5. Foundation artificial intelligence models for health recognition by use of face photographs (FAHR-Face)
The Lancet Digital Health, 1 Oct 2026 · group author: Leonard Nürnberg (first author Fridolin Haugg)

**LinkedIn post**

A foundation model trained on more than 40 million face photographs estimated biological age with a mean error of 5.1 years and, in cancer patients, predicted survival independently of clinical factors.

FAHR-Face was fine-tuned for two tasks: age estimation on ten public image datasets, and survival prediction on 34,363 photographs of patients with cancer. Robustness to cosmetic surgery, make-up, pose and lighting was tested, as was what the model attends to. Both models were evaluated in two independent cancer cohorts with multivariable Cox models adjusted for clinical prognostic factors.

The highest-risk quartile had more than three times the mortality of the lowest (adjusted hazard ratio 3.23). Results held across age, sex, race and cancer subgroups.

Why it matters: a photograph is non-invasive and already in many patient records; the model gives a prognostic signal that clinical variables do not capture.

Limitation: validation was in cancer cohorts; use in other populations and the ethics of face-based prognosis need separate work [check].

Paper: https://doi.org/10.1016/j.landig.2026.101056
Full text: open access

**Short version**
FAHR-Face, trained on 40 million face photos, estimates biological age within 5.1 years and predicts survival in cancer patients beyond clinical factors (adjusted HR 3.23). https://doi.org/10.1016/j.landig.2026.101056

---

### Notes for the review
- Paper 2's stored abstract is cut at 1,500 characters, so its result is missing. The pipeline will store full abstracts from now on.
- Wenjie Liang is first author of paper 1 and on the staff page, but OpenAlex recorded no affiliation for him on it, so he is not listed as a group author. Adding his ORCID to the staff profile fixes this.
- Paper 5 has one group author among 17; whether the group should promote it is a judgment call for the approval list.

---

## Images (added 2026-10-23)

Every drafted paper gets a **card** (1200×627) with the main finding as headline, the title, journal, year and group
authors. A **figure from the paper** is only used when the licence allows it (CC BY family, not ND) and only when it
shows the main finding; methods figures are rejected.

| Paper | Card | Figure | Why |
|---|---|---|---|
| Frontiers, federated survival analysis | yes | Figure 3, forest plot | Shows the finding directly: hazard ratios identical for standard and binned Cox models. Caption for LinkedIn: "Each row is a known risk factor for survival in head and neck cancer, and each colour is a different version of the model: one standard, two that protect patient privacy. The dots land in the same place. Protecting privacy did not change the answers." |
| Medical Oncology, ITH review | yes | none | Only extractable figure is the PRISMA flow diagram: methods, not the finding. |
| npj Breast Cancer | yes | none | Licence CC BY-NC-ND: no reuse of figures. |
| Lancet Digital Health, FAHR-Face | yes | none | Licence CC BY-NC-ND: no reuse of figures. |
| JMIR AI, reporting standards | yes | none | JMIR serves no PDF to automated requests. |

With the API key in place, the same selection and description step runs automatically with Claude; without it, the
largest figure is taken and marked "unchecked pick" so a person always looks before posting.
