> **Revised 2026-10-27** after feedback from Joshi: posts no longer mention limitations (advert tone), and the headline of
> "From registration to insight" was wrong ("now informs young patients' care" overstated a proof of concept); it is now
> "A UK cancer registry joins a European data network". The current texts are in the social post studio on the website.

# LinkedIn draft samples — Joshi Hogenboom, 2024–2026

Written from the abstracts only, in the format the weekly pipeline produces (same system prompt as `pubpulse/social.py`),
for a quality check before the pipeline gets an API key. `[check]` marks a claim to verify against the full paper
before posting. Nothing is posted automatically: a person copies, edits and posts.

---

## 1. From registration to insight: how STRONG AYA transforms registry data to enhance decision-support tools for adolescent and young adult oncology
ESMO Real World Data and Digital Oncology, 2026-09-15 · group authors: Joshi Hogenboom, Varsha Gouthamchand, Aiara Lobo Gomes, Andre Dekker, Leonard Wee · Joshi author 2 of 21

**Card headline:** A UK cancer registry now informs young patients' care

**LinkedIn post**

A regional cancer registry can feed a European data network and bring the results back into the consultation room for adolescents and young adults with cancer.

Work by Joshi Hogenboom, Varsha Gouthamchand, Aiara Lobo Gomes, Andre Dekker and Leonard Wee with colleagues in the STRONG AYA consortium and the University of Leeds.

Data from the Yorkshire Specialist Register of Cancer in Children and Young People were loaded into an open-source federated learning infrastructure, where they are analysed together with data from other consortium members without being pooled. The results flow into PROMPT, software from Leeds, and appear in the patient's electronic health record.

Why it matters: clinicians can see a patient's reported outcomes over time next to summary results from the wider consortium, which can support conversations with young patients and, later, research and policy.

Limitation: this is a proof of concept; whether it improves outcomes for young patients has not been measured yet.

Published in ESMO Real World Data and Digital Oncology.

#ClinicalDataScience #MaastrichtUniversity #AYACancer

**First comment**

From registration to insight: how STRONG AYA transforms registry data to enhance decision-support tools for adolescent and young adult oncology  
Paper: https://doi.org/10.1016/j.esmorw.2026.100764  
Full text: https://doi.org/10.1016/j.esmorw.2026.100764

**Short version**
A UK registry for young people with cancer now feeds the STRONG AYA federated network, and the results show up in the patient record during consultations. A proof of concept. https://doi.org/10.1016/j.esmorw.2026.100764

Card: `data/social/images/W7213226988-card.png`

---

## 2. Knowledge Representation of a Multicenter Adolescent and Young Adult Cancer Infrastructure: Development of the STRONG AYA Knowledge Graph
JCO Clinical Cancer Informatics, 2026-01-01 · group authors: Joshi Hogenboom, Varsha Gouthamchand, Andre Dekker, Leonard Wee, Johan van Soest, Aiara Lobo Gomes · Joshi author 1 of 12

**Card headline:** Making messy cancer data talk without forcing one format

**LinkedIn post**

Hospital data in different formats can be made to work together without rewriting them into one rigid standard, using knowledge graphs.

Work by Joshi Hogenboom, Varsha Gouthamchand, Andre Dekker, Leonard Wee, Johan van Soest and Aiara Lobo Gomes with colleagues in the STRONG AYA project.

STRONG AYA is building a federated data infrastructure for adolescents and young adults with cancer, a rare and scattered group whose data arrive in many formats. The team converted the structured data into linked data (RDF triples) with a semantic web tool [check: tool name, missing from the stored abstract] and used a mapping and annotation helper to query local terminologies as they are, without changing them. Graphs and mappings are published online.

Why it matters: rare-disease research needs data from many centres; this makes them reusable without every centre adopting one schema.

Limitation: this is a demonstration on the project's own data; it does not yet show results from analyses run on it.

Published in JCO Clinical Cancer Informatics.

#ClinicalDataScience #MaastrichtUniversity #FAIRData

**First comment**

Knowledge Representation of a Multicenter Adolescent and Young Adult Cancer Infrastructure: Development of the STRONG AYA Knowledge Graph  
Paper: https://doi.org/10.1200/cci-25-00177  
Full text: https://ascopubs.org/doi/pdf/10.1200/CCI-25-00177

**Short version**
Knowledge graphs make differently formatted data on young adults with cancer interoperable across centres, without forcing one rigid schema. From the STRONG AYA project. https://doi.org/10.1200/cci-25-00177

Card: `data/social/images/W7124178724-card.png`

---

## 3. STRONG AYA Algorithm Review Guidelines
Zenodo (CERN European Organization for Nuclear Research), 2025-07-29 · group authors: Leonard Wee, Joshi Hogenboom · Joshi author 3 of 4

**Card headline:** Quality checks for every algorithm in a federated network

**LinkedIn post**

Every algorithm that runs on the STRONG AYA federated network now goes through a defined quality assurance process.

Work by Leonard Wee and Joshi Hogenboom with colleagues in the STRONG AYA consortium.

The guidelines set out how algorithms built for Vantage6, the open-source platform that lets analyses travel to the data instead of the data travelling to the analyst, are reviewed before they are used in STRONG AYA. [check: what the review covers, e.g. code review, testing, privacy checks; the stored summary is one sentence]

Why it matters: in a federated network nobody sees the raw data, so trust rests on the algorithms themselves. A shared review process makes that trust explicit and repeatable.

Limitation: this is a process document; it does not report how many algorithms were reviewed or what the reviews found [check].

Published on Zenodo.

#ClinicalDataScience #MaastrichtUniversity #FederatedLearning

**First comment**

STRONG AYA Algorithm Review Guidelines  
Paper: https://doi.org/10.5281/zenodo.22206390  
Full text: https://doi.org/10.5281/zenodo.22206390

**Short version**
STRONG AYA sets out a quality assurance process for the Vantage6 algorithms that run on its federated network for young adults with cancer. https://doi.org/10.5281/zenodo.22206390

Card: `data/social/images/W7204787670-card.png`

---

## 4. Actionability of Synthetic Data in a Heterogeneous and Rare Health Care Demographic: Adolescents and Young Adults With Cancer
JCO Clinical Cancer Informatics, 2024-12-01 · group authors: Joshi Hogenboom, Aiara Lobo Gomes, Andre Dekker, Leonard Wee · Joshi author 1 of 6

**Card headline:** Synthetic data works, but sample size changes the trade-offs

**LinkedIn post**

Synthetic patient data can be useful even for a rare, varied group, but the number of real patients behind it changes its quality and privacy risk.

Work by Joshi Hogenboom, Aiara Lobo Gomes, Andre Dekker and Leonard Wee with colleagues.

From a population-based cohort of 3,735 adolescents and young adults with cancer, the team drew 13 training sets and generated synthetic data with four generators from the open-source Synthetic Data Vault. Each synthetic set was compared with its real data on veracity, utility and privacy.

All four generators produced usable data when the synthetic set was about as large as the real one. Larger synthetic sets were more faithful but generally riskier for privacy; fewer training patients sped up veracity but partly worsened privacy.

Why it matters: synthetic data is a candidate for sharing and enlarging scarce data, but only with consistent checks and a deliberate sample size.

Limitation: one cohort and generators from a single library were tested.

Published in JCO Clinical Cancer Informatics.

#ClinicalDataScience #MaastrichtUniversity #SyntheticData

**First comment**

Actionability of Synthetic Data in a Heterogeneous and Rare Health Care Demographic: Adolescents and Young Adults With Cancer  
Paper: https://doi.org/10.1200/cci.24.00056  
Full text: https://doi.org/10.1200/cci.24.00056

**Short version**
Synthetic data for 3,735 young adults with cancer: all four generators gave usable data, but larger synthetic sets traded privacy for fidelity. Sample size matters. https://doi.org/10.1200/cci.24.00056

Card: `data/social/images/W4404946484-card.png`

---

## 5. An Overview of Real-World Data Infrastructure for Cancer Research
Clinical Oncology, 2024-03-19 · group authors: Joshi Hogenboom, Johan van Soest, Andre Dekker · Joshi author 6 of 10

**Card headline:** Real-world cancer data is already usable, at every scale

**LinkedIn post**

Research with real-world cancer data is already possible, from a single hospital database up to international federated studies, as long as the question matches the scale.

Work by Joshi Hogenboom, Johan van Soest and Andre Dekker with colleagues, led from the UK.

The paper reviews current real-world data resources and how researchers can get access to them: local hospital research databases, regional care records, national repositories, and federated learning for international collaboration. Case studies, mainly from the UK, show the infrastructure and governance needed at each scale.

Why it matters: real-world data can fill evidence gaps where clinical trials do not exist, and access is often named as the main barrier. The overview shows which routes exist today.

Limitation: the examples are mainly from the UK, so the governance routes may differ elsewhere.

Published in Clinical Oncology.

#ClinicalDataScience #MaastrichtUniversity #RealWorldData

**First comment**

An Overview of Real-World Data Infrastructure for Cancer Research  
Paper: https://doi.org/10.1016/j.clon.2024.03.011  
Full text: https://doi.org/10.1016/j.clon.2024.03.011

**Short version**
From hospital databases to international federated studies: an overview of real-world data infrastructure for cancer research, with UK case studies on access and governance. https://doi.org/10.1016/j.clon.2024.03.011

Card: `data/social/images/W4392946919-card.png`

---

## 6. Getting real about synthetic data ethics
EMBO Reports, 2024-02-22 · group authors: Joshi Hogenboom, Leonard Wee, Andre Dekker · Joshi author 2 of 7

**Card headline:** Synthetic data is not ethics-free

**LinkedIn post**

Synthetic data is often presented as the way around hard data sharing, but it raises its own ethical questions that deserve serious attention.

Work by Joshi Hogenboom, Leonard Wee and Andre Dekker with colleagues.

In this commentary the authors look at synthetic data, artificially generated records that mimic real patients, as an alternative when collecting or sharing real data is not feasible or too costly. They argue that it brings distinct ethical issues of its own. [check: which issues the piece names; the stored summary is one sentence]

Why it matters: synthetic data is spreading quickly in health research, and treating it as automatically safe could hide new risks.

Limitation: this is a perspective piece, not an empirical study.

Published in EMBO Reports.

#ClinicalDataScience #MaastrichtUniversity #DataEthics

**First comment**

Getting real about synthetic data ethics  
Paper: https://doi.org/10.1038/s44319-024-00101-0

**Short version**
Synthetic data can stand in when real data cannot be shared, but it raises its own ethical issues. A commentary in EMBO Reports. https://doi.org/10.1038/s44319-024-00101-0

Card: `data/social/images/W4392049920-card.png`
