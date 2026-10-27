const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../site/social-editor.js"), "utf8"), context);
const { parseAnswer, buildPrompt } = context.window.PubpulseSocial;
const answer = {
  headline: "A useful research finding",
  post: 'A finding with "quoted text", {braces}, and a backslash \\.\n\nA second paragraph.',
  comment: "Paper title\nPaper: https://doi.org/10.1000/example",
  short: "Two short sentences. https://doi.org/10.1000/example",
};
const comparable = value => JSON.parse(JSON.stringify(value));

test("imports complete, pretty-printed JSON without altering its text", () => {
  assert.deepEqual(comparable(parseAnswer(JSON.stringify(answer, null, 2))), answer);
});

test("imports JSON copied with code fences or surrounding chat text", () => {
  for (const text of [
    "```json\n" + JSON.stringify(answer, null, 2) + "\n```",
    "Here is your draft:\n" + JSON.stringify(answer, null, 2) + "\nReady to import.",
  ]) assert.deepEqual(comparable(parseAnswer(text)), answer);
});

test("repairs literal newlines inside strings while preserving pretty-printed JSON structure", () => {
  const invalidJSON = JSON.stringify(answer, null, 2).replace(/\\n/g, "\n");
  assert.throws(() => JSON.parse(invalidJSON));
  assert.deepEqual(comparable(parseAnswer(invalidJSON)), answer);
});

test("rejects incomplete or incorrectly typed drafts instead of mixing them with previous content", () => {
  for (const invalid of [
    { post: "Only a post" },
    { ...answer, headline: 42 },
    { ...answer, comment: null },
    { ...answer, short: "   " },
    [answer],
    "not JSON",
  ]) assert.equal(parseAnswer(JSON.stringify(invalid)), null);
});

test("supports older section replies and preserves Unicode", () => {
  const unicode = { ...answer, headline: "Maastricht’s research – déjà vu" };
  const sections = Object.entries(unicode).map(([key, value]) => `### ${key.toUpperCase()}\n${value}`).join("\n\n");
  assert.deepEqual(comparable(parseAnswer(sections)), unicode);
});

test("chooses the final complete reply when chat text includes an earlier example", () => {
  const actual = { ...answer, headline: "The actual finding" };
  const response = "Example:\n" + JSON.stringify(answer) + "\nYour draft:\n" + JSON.stringify(actual);
  assert.deepEqual(comparable(parseAnswer(response)), actual);
});

test("copied prompts include the current paper and one unambiguous JSON output contract", () => {
  const paper = { title: "Current paper", journal: "Current journal", publication_date: "2026-10-27", group_authors: ["Researcher A"], authors: ["Researcher A"], link: "https://doi.org/10.1000/current", abstract: "A specific, measured finding." };
  const prompt = buildPrompt(paper, '### HEADLINE\nKeep it faithful.\nOutput exactly the four sections, nothing else.');
  assert(prompt.includes(paper.title));
  assert(prompt.includes(paper.abstract));
  assert(prompt.includes(paper.link));
  assert(prompt.includes("Researcher A"));
  assert(!prompt.includes("### HEADLINE"));
  assert(!prompt.includes("Output exactly the four sections"));
  const example = prompt.trim().split("\n").at(-1);
  assert.deepEqual(Object.keys(JSON.parse(example)), ["headline", "post", "comment", "short"]);
});

test("fallback prompts still request complete JSON when shared writing instructions are absent", () => {
  const prompt = buildPrompt({ title: "Paper", authors: [], group_authors: [], link: "https://doi.org/10.1000/paper" });
  assert(prompt.includes("Use only the supplied abstract"));
  assert(prompt.includes("Every value must be a non-empty string"));
  assert.equal(Object.keys(JSON.parse(prompt.trim().split("\n").at(-1))).length, 4);
});
