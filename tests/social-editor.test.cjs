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

test("copied prompts are the instructions once, followed by the current paper", () => {
  const paper = { title: "Current paper", journal: "Current journal", publication_date: "2026-10-27", group_authors: ["Researcher A"], authors: ["Researcher A"], link: "https://doi.org/10.1000/current", abstract: "A specific, measured finding." };
  const prompt = buildPrompt(paper, "Shared writing rules.");
  assert(prompt.startsWith("Shared writing rules.\n"));
  assert.equal(prompt.split("Shared writing rules.").length, 2);
  for (const part of [paper.title, paper.journal, paper.link, "Researcher A"]) assert(prompt.includes(part));
  assert(prompt.trim().endsWith(paper.abstract));
  assert(!prompt.includes("Open-access link"));
});

test("fallback prompts ask for the four-key JSON code block when shared instructions are absent", () => {
  const prompt = buildPrompt({ title: "Paper", authors: [], group_authors: [], link: "https://doi.org/10.1000/paper" });
  const block = prompt.match(/```json\n(.*)\n```/)[1];
  assert.deepEqual(Object.keys(JSON.parse(block)), ["headline", "post", "comment", "short"]);
  assert(prompt.includes("paste the abstract here"));
});

test("imports a reply given as a JSON code block with literal line breaks", () => {
  const reply = '```json\n{"headline": "H", "post": "First.\n\nSecond.", "comment": "C", "short": "S"}\n```';
  assert.deepEqual(comparable(parseAnswer(reply)), { headline: "H", post: "First.\n\nSecond.", comment: "C", short: "S" });
});
