import { test, describe } from "node:test";
import assert from "node:assert";
import { chunkText, protectFrontMatter, detectFigureTableIssues, detectCitationIssues, dedupeAndArbitrate } from "../src/utils/textAnalysis";
import { IssueSchema, Issue } from "../src/models/IssueSchema";

describe("Text Analysis Utilities", () => {
  test("chunkText should split text into smaller chunks", () => {
    const text = "A".repeat(5000) + "\n\n" + "B".repeat(5000);
    const chunks = chunkText(text, 8000);
    assert.strictEqual(chunks.length, 2);
    assert.ok(chunks[0].startsWith("A"));
    assert.ok(chunks[1].startsWith("B"));
  });

  test("protectFrontMatter should flag destructive edits to front matter", () => {
    const text = "Author: John Doe\nAffiliation: University of Example\nAbstract...";
    const badEdit = "Some random new text";
    const protection = protectFrontMatter(text, badEdit);
    assert.strictEqual(protection.blocked, true);
    assert.ok(protection.reason?.includes("front-matter"));

    const safeEdit = text + "\nExtra info.";
    const safeProtection = protectFrontMatter(text, safeEdit);
    assert.strictEqual(safeProtection.blocked, false);
  });

  test("detectFigureTableIssues should find orphans and unreferenced declarations", () => {
    const text = "As shown in Fig. 1. \n\nFig 2: A nice chart.\nTable 1: Data.";
    const figs = detectFigureTableIssues(text);
    
    assert.ok(figs.mentions.figures.includes("fig 1"));
    assert.ok(figs.declarations.figures.includes("fig 2"));
    assert.ok(figs.declarations.tables.includes("table 1"));
    
    assert.ok(figs.issues.orphans.includes("fig 1"));
    assert.ok(figs.issues.unreferenced.includes("fig 2"));
    assert.ok(figs.issues.unreferenced.includes("table 1"));
  });

  test("detectCitationIssues should find dangling and unused citations", () => {
    const text = "This is a claim [1, 2]. Another claim [5].\n\nReferences\n[1] Paper A\n[2] Paper B\n[3] Paper C";
    const cites = detectCitationIssues(text);
    
    assert.deepStrictEqual(cites.inTextCitations, [1, 2, 5]);
    assert.deepStrictEqual(cites.declaredReferences, [1, 2, 3]);
    
    assert.deepStrictEqual(cites.issues.danglingCitations, [5]);
    assert.deepStrictEqual(cites.issues.unusedReferences, [3]);
  });
  
  test("dedupeAndArbitrate should remove exact duplicates and sort by severity", () => {
    const issues: Issue[] = [
      { id: "1", stage: "methods", section: "Methods", location: "loc", severity: "low", confidence: 0.9, issue_type: "typo", evidence: "ev", suggested_fix: "fix", localizable: true, render_mode: "comment" },
      { id: "2", stage: "methods", section: "Methods", location: "loc", severity: "high", confidence: 0.9, issue_type: "typo", evidence: "ev", suggested_fix: "fix", localizable: true, render_mode: "comment" },
      { id: "3", stage: "methods", section: "Methods", location: "loc", severity: "high", confidence: 0.9, issue_type: "typo", evidence: "ev", suggested_fix: "fix", localizable: true, render_mode: "comment" }
    ];
    
    const resolved = dedupeAndArbitrate(issues);
    assert.strictEqual(resolved.length, 1);
    assert.strictEqual(resolved[0].severity, "high");
  });
});

describe("Issue Schema Validation", () => {
  test("should validate a correct issue object", () => {
    const validIssue = {
      id: "123",
      stage: "methods",
      section: "Methods",
      location: "Paragraph 2",
      severity: "high",
      confidence: 0.9,
      issue_type: "missing_control",
      evidence: "No mention of negative control.",
      suggested_fix: "Add negative control experiment.",
      localizable: true,
      render_mode: "comment"
    };
    
    const result = IssueSchema.safeParse(validIssue);
    assert.strictEqual(result.success, true);
  });

  test("should fail on invalid severity", () => {
    const invalidIssue = {
      id: "123",
      stage: "methods",
      section: "Methods",
      location: "Paragraph 2",
      severity: "super_high", // Invalid
      confidence: 0.9,
      issue_type: "missing_control",
      evidence: "No mention of negative control.",
      suggested_fix: "Add negative control experiment.",
      localizable: true,
      render_mode: "comment"
    };
    
    const result = IssueSchema.safeParse(invalidIssue);
    assert.strictEqual(result.success, false);
  });
});
