import { Issue } from '../models/IssueSchema';

export function chunkText(text: string, maxChars: number = 8000): string[] {
  const chunks: string[] = [];
  let currentChunk = '';
  const paragraphs = text.split(/\n\s*\n/);
  
  for (const p of paragraphs) {
    if (currentChunk.length + p.length > maxChars && currentChunk.length > 0) {
      chunks.push(currentChunk.trim());
      currentChunk = '';
    }
    currentChunk += p + '\n\n';
  }
  
  if (currentChunk.trim().length > 0) {
    chunks.push(currentChunk.trim());
  }
  
  return chunks;
}

export function protectFrontMatter(originalText: string, editSuggestion: string): { blocked: boolean; reason?: string } {
  const frontMatterKeywords = ['author', 'affiliation', 'acknowledgment', 'funding', 'correspondence', 'email'];
  const lowerOriginal = originalText.toLowerCase().substring(0, 1500); // Usually front matter is at the beginning

  // Very simplistic check: If the original text seems to be front matter and the edit is destructive
  if (frontMatterKeywords.some(kw => lowerOriginal.includes(kw))) {
    if (editSuggestion.length < originalText.length * 0.5) {
      return { blocked: true, reason: 'Suspected destructive edit to front-matter (author/affiliation/funding).' };
    }
  }

  return { blocked: false };
}

export function detectFigureTableIssues(text: string) {
  // Regex to find actual figure captions / declarations
  const figDeclRegex = /^fig(?:ure)?\.?\s*\d+[\.:]/gim;
  const tabDeclRegex = /^table\.?\s*\d+[\.:]/gim;
  
  const figDecls = Array.from(new Set((text.match(figDeclRegex) || []).map(m => m.toLowerCase().replace(/[\.:]/g, '').replace(/\s+/g, ' '))));
  const tabDecls = Array.from(new Set((text.match(tabDeclRegex) || []).map(m => m.toLowerCase().replace(/[\.:]/g, '').replace(/\s+/g, ' '))));

  // Remove declaration lines so they aren't double-counted as mentions
  const bodyText = text.replace(/^fig(?:ure)?\.?\s*\d+[\.:].*$/gim, '').replace(/^table\.?\s*\d+[\.:].*$/gim, '');

  // Regex to find body mentions of figures and tables
  const figMentionRegex = /fig(?:ure)?\.?\s*\d+[a-z]?/gi;
  const tabMentionRegex = /table\.?\s*\d+[a-z]?/gi;

  const figMentions = Array.from(new Set((bodyText.match(figMentionRegex) || []).map(m => m.toLowerCase().replace(/[\.:]/g, '').replace(/\s+/g, ' '))));
  const tabMentions = Array.from(new Set((bodyText.match(tabMentionRegex) || []).map(m => m.toLowerCase().replace(/[\.:]/g, '').replace(/\s+/g, ' '))));
  
  const orphans = [
    ...figMentions.filter(m => !figDecls.includes(m)),
    ...tabMentions.filter(m => !tabDecls.includes(m))
  ];
  
  const unreferenced = [
    ...figDecls.filter(d => !figMentions.includes(d)),
    ...tabDecls.filter(d => !tabMentions.includes(d))
  ];

  return {
    mentions: { figures: figMentions, tables: tabMentions },
    declarations: { figures: figDecls, tables: tabDecls },
    issues: {
      orphans: orphans,
      unreferenced: unreferenced
    }
  };
}

export function detectCitationIssues(text: string) {
  const refSectionMatch = text.match(/references\s*\n([\s\S]*)/i);
  const bodyText = refSectionMatch ? text.substring(0, refSectionMatch.index) : text;
  
  // Extract in-text numeric citations from body only
  const bracketRegex = /\[\s*\d+(?:\s*,\s*\d+|\s*-\s*\d+)*\s*\]/g;
  const inTextMatches = bodyText.match(bracketRegex) || [];
  
  const extractedNumbers = new Set<number>();
  inTextMatches.forEach(match => {
    const nums = match.replace(/\[|\]/g, '').split(/[,]/).map(s => s.trim());
    nums.forEach(n => {
      if (n.includes('-')) {
        const [start, end] = n.split('-').map(Number);
        for (let i = start; i <= end; i++) extractedNumbers.add(i);
      } else {
        extractedNumbers.add(Number(n));
      }
    });
  });
  
  const declaredNumbers = new Set<number>();
  
  if (refSectionMatch) {
    const refsText = refSectionMatch[1];
    const declRegex = /^\[(\d+)\]/gm;
    let match;
    while ((match = declRegex.exec(refsText)) !== null) {
      declaredNumbers.add(Number(match[1]));
    }
  }
  
  const danglingCitations = Array.from(extractedNumbers).filter(n => !declaredNumbers.has(n));
  const unusedReferences = Array.from(declaredNumbers).filter(n => !extractedNumbers.has(n));

  return {
    inTextCitations: Array.from(extractedNumbers).sort((a,b)=>a-b),
    declaredReferences: Array.from(declaredNumbers).sort((a,b)=>a-b),
    issues: {
      danglingCitations,
      unusedReferences
    }
  };
}

export function dedupeAndArbitrate(issues: Issue[]): Issue[] {
  const seen = new Set<string>();
  const arbitrated: Issue[] = [];

  // Sort by severity (critical > high > medium > low) and confidence
  const severityWeight: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
  
  issues.sort((a, b) => {
    const weightDiff = severityWeight[b.severity] - severityWeight[a.severity];
    if (weightDiff !== 0) return weightDiff;
    return b.confidence - a.confidence;
  });

  for (const issue of issues) {
    // Basic deduplication: similar suggested_fix in same section
    const key = `${issue.section}|${issue.issue_type}|${issue.location}`;
    if (!seen.has(key)) {
      seen.add(key);
      arbitrated.push(issue);
    }
  }

  return arbitrated;
}

