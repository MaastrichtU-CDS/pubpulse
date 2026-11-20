# Reference: how others announce a paper — what gets attention, what stays faithful

Collected 29 Oct 2026 to tune the social post prompt (`CHAT_PROMPT` and `SYSTEM_PROMPT` in `pubpulse/social.py`).
Every paper below was checked against its abstract (OpenAlex / PubMed). Engagement counts were read on 29 Oct 2026.
Only links, opening lines and our own analysis are kept here; read the full posts at the links.

## What the evidence says about hype

- **Sumner et al., BMJ 2014** ([10.1136/bmj.g7015](https://doi.org/10.1136/bmj.g7015)): in 462 UK university press
  releases, a third claimed causation from correlational data and a third drew human conclusions from animal work.
  Exaggeration in the release carried into the news, but did **not** earn more news coverage.
- **Sumner et al., PLOS ONE 2016** ([10.1371/journal.pone.0168217](https://doi.org/10.1371/journal.pone.0168217)):
  the same pattern for journal press releases; caveats in the release carried into the news without reducing uptake.
- **Adams et al., BMC Medicine 2019** ([10.1186/s12916-019-1324-7](https://doi.org/10.1186/s12916-019-1324-7)):
  randomised trial of 312 press releases. Headlines aligned with the evidence led to better-aligned news (60% vs 32%)
  with the same uptake (55% vs 55%).

So faithfulness costs no reach. For AI papers the usual jumps are: a retrospective result told as clinical benefit;
a surrogate metric (Dice, AUC, dose) told as patient outcome; "matched the variability between experts" told as
"beats doctors"; alternative operating points merged into one claim; ratios the paper never reports.

## Posts by research groups (LinkedIn unless stated)

| # | Poster · paper | Reactions | Opening line | Verdict vs abstract |
|---|---|---|---|---|
| 1 | [Fridolin Haugg](https://www.linkedin.com/posts/fridolin-haugg_the-paper-ive-spent-most-of-my-phd-working-activity-7518087057429331968-vXnq) · FAHR-Face, Lancet Digit Health 2026 ([doi](https://doi.org/10.1016/j.landig.2026.101056)) | 371 · 55 comments | "The paper I've spent most of my PhD working on is now published…" | Slightly stronger: "from a single selfie", but the model used clinical photographs |
| 2 | [Ray Mak](https://www.linkedin.com/posts/ray-mak_foundation-artificial-intelligence-models-activity-7518272435465510912-H7q6) · same paper | 44 | "Pleased to share our new study in The Lancet Digital Health…" | Faithful |
| 3 | [Hugo Aerts](https://www.linkedin.com/posts/hugoaerts_can-a-simple-selfie-reveal-something-about-activity-7518328973391515648-XTcA) · same paper | 43 | "Can a simple selfie reveal something about your health?" | Slightly stronger ("suggests it can!", "try it yourself") |
| 4 | [Bo Wang](https://www.linkedin.com/posts/bo-wang-a6065240_the-best-way-to-start-the-week-is-to-find-activity-7155410286571585536-IHCD) · MedSAM, Nat Commun 2024 ([doi](https://doi.org/10.1038/s41467-024-44824-z)) | 1,594 | "…our MedSAM is finally published today in Nature Communications!" | Slightly stronger ("first", "Clinical Translation!!"); numbers accurate |
| 5 | [Jakob N. Kather](https://www.linkedin.com/posts/jnkath_swarm-learning-for-decentralized-artificial-activity-6924497046443851776-zH88) · swarm learning, Nat Med 2022 ([doi](https://doi.org/10.1038/s41591-022-01768-5)) | 324 | "We show that multiple institutions can co-train medical #AI models without sharing any raw data." | Faithful (small generalisation) |
| 6 | [NKI](https://www.linkedin.com/posts/the-netherlands-cancer-institute_breakthrough-in-treatment-for-stomach-and-activity-7150066406703734784-YobS) · PANDA trial, Nat Med 2024 ([doi](https://doi.org/10.1038/s41591-023-02758-x)) | 416 | "Patients with cancer in the stomach… appear to respond well to a new treatment type…" | Body slightly stronger; link card "Breakthrough…" overstated for 20 patients |
| 7 | [Alexander Schubert](https://www.linkedin.com/posts/alexander-schubert-84172ab1_nature-activity-7476666574381268993-gsm8) · ECG biomarker for sudden cardiac death, Nature 2026 ([doi](https://doi.org/10.1038/s41586-026-10674-6)) | 158 · 27 expert comments | "Every year in the US alone 300,000–400,000 people drop dead without prior warning." | Faithful |
| 8 | [Pranav Rajpurkar](https://www.linkedin.com/posts/pranavrajpurkar_can-ai-built-for-adults-learn-to-care-for-activity-7515987866179608576-iomJ) · adult X-ray AI for neonatal ICUs, Nat Biomed Eng 2026 ([doi](https://doi.org/10.1038/s41551-026-01812-6)) | 76 | "Can AI built for adults learn to care for newborns?" | Faithful, more cautious than the abstract |
| 9 | [Ray Mak](https://www.linkedin.com/posts/ray-mak_thymic-radiation-is-associated-with-worse-activity-7498187079386877952-120B) · thymic radiation in NSCLC, Ann Oncol 2026 ([doi](https://doi.org/10.1016/j.annonc.2026.07.001)) | 38 | "Pleased to share our new study in Annals of Oncology…" | Faithful; ~490 words, too long |
| 10 | [DIAG Radboudumc, news page](https://www.diagnijmegen.nl/news/pi-cai-lancet/) · PI-CAI, Lancet Oncol 2024 ([doi](https://doi.org/10.1016/S1470-2045(24)00220-1)) | – | "Primary outcomes of the PI-CAI challenge published in The Lancet Oncology" | Faithful; names the comparator ("a pool of 62 radiologists") |
| 11 | [NKI, news page](https://www.nki.nl/news-events/news/ai-model-proves-to-be-a-heavyweight-in-tumor-assessment) · ARTIMES, Lancet Oncol 2026 ([doi](https://doi.org/10.1016/S1470-2045(26)00084-7)) | – | "AI model proves to be a heavyweight in tumor assessment" | Overstated: compared response criteria, not AI vs physicians; drops "pending prospective validation" |

Same paper, three posters (1–3): 371 vs 44 vs 43 reactions. The poster's network and the journal matter a lot and
cannot be copied; the opening line can.

## Press releases about AI papers

| Organisation · paper | Headline | Verdict |
|---|---|---|
| [Lund University](https://www.eurekalert.org/news-releases/1072522) · MASAI, Lancet Digit Health 2025 | "AI-supported breast cancer screening – new results suggest even higher accuracy" | Faithful: keeps the abstract's "suggest" |
| [Northwestern](https://www.eurekalert.org/news-releases/1089131) · iSeg, npj Precis Oncol 2025 | "AI matches doctors in mapping lung tumors for radiation therapy" | Faithful: the abstract says it matched inter-observer variability |
| [BIT Press](https://www.eurekalert.org/news-releases/1131388) · real-time AI planning for NPC, 2026 | (paper title) | Faithful: concrete numbers, single-centre stated |
| [The Lancet](https://www.eurekalert.org/news-releases/1114399) · MASAI interval cancers, 2026 | "…results in fewer aggressive and advanced breast cancers" | Overstated "12% reduction": rate ratio 0.88, CI 0.65–1.18 |
| [Radboudumc](https://www.radboudumc.nl/en/news-items/2024/ai-better-detects-prostate-cancer-on-mri-than-radiologists) · PI-CAI, 2024 | "AI better detects prostate cancer on MRI than radiologists" | Slightly stronger: merges two alternative operating points |
| [Moffitt](https://www.eurekalert.org/news-releases/1072179) · human–AI decisions, Nat Commun 2025 | "…AI boosts efficacy of cancer treatment…" | Overstated: a study of clinician behaviour, no efficacy measured |
| [UCLA](https://sciencedaily.com/releases/2024/06/240611130432.htm) · prostate contouring, J Urol 2024 | "AI model may yield better outcomes for prostate cancer" | Overstated: "45 times more accurate" is a ratio of margin rates |
| [Maastricht University](https://www.maastrichtuniversity.nl/nl/nieuws/kunstmatige-intelligentie-kan-longtumor-beter-afbakenen-dan-radioloog) · lung tumour segmentation, Nat Commun 2022 | "Kunstmatige intelligentie kan longtumor beter afbakenen dan radioloog" | Slightly stronger: the abstract says faster and more reproducible |

## Patterns

**What earns attention**
- A first line with human stakes: a personal milestone ("the paper I've spent most of my PhD on") or the size of the
  clinical problem ("300,000–400,000 people… without prior warning"). "Pleased to share our new study in [journal]"
  reached 38–44 reactions.
- One concrete, picturable idea per post.
- Something readers can use or forward: code, data, a plugin, a model. MedSAM's 1,594 reactions came with comments
  tagging colleagues.
- Short is fine: Kather reached 324 reactions with about 100 words.
- Tagged co-authors and institutions; each tag reaches another network.

**What keeps a post faithful**
- Reuse the abstract's own verb, comparator and hedge ("associated with", "matched", "suggest").
- Name the comparator and scale ("62 radiologists in 45 centres", "29 of 30 hospitals").
- One sentence on the design, folded into the claim ("in a retrospective study of…"), or a next-step line
  ("Next, we will test this prospectively") that reads as momentum, not weakness.
- The headline or link card is what gets shared, and it is often the least faithful part (NKI, Moffitt, UCLA).
- Avoid: "breakthrough", "first (in the world)", "beats doctors", "boosts", "try it yourself" for a research model,
  and framings the data do not support ("selfie" when the photos were clinical).

**Doing both:** Schubert (7) and Kather (5). Rajpurkar (8) is the best template for faithful wording.

## Guidance worth knowing

- Karolinska Institutet, [communicating about your research](https://staff.ki.se/tools-and-support/communication-tools-and-support/news-press-and-media/communicating-with-a-wider-audience-about-your-research):
  key points first, late-teens reading level, hashtags sparingly; on LinkedIn, posts with links get less visibility.
- Academy of Medical Sciences / Science Media Centre, [press release labels](https://www.sciencemediacentre.org/wp-content/uploads/2024/04/AMS-press-release-labelling-system-GUIDANCE.pdf):
  causal verbs by study design ("reduces" only for experimental evidence; "may", "is associated with" otherwise).
- [COMPASS Message Box](https://www.compassscicomm.org/leadership-development/the-message-box/) and
  [ABT, "And, But, Therefore"](https://www.sesync.org/resources/communications-toolkit-and-therefore-statement).
- LERU, [Communicating with integrity](https://www.leru.org/files/Publications/Communicating-with-intergrity_LERU-paper.pdf) (2024).
- Maastricht University: [social media guidelines](https://www.maastrichtuniversity.nl/node/58897) and the
  [UM writing style guide](https://www.maastrichtuniversity.nl/file/umwritingstyleguidepdf) (British spelling,
  address the reader, short sentences). Maastro and Maastricht UMC+ have no public writing guide; ask their
  communication teams for house rules and good examples.
