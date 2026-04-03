import { getFsImplementation } from './fsOperations.js';
import { join } from 'path';
import { getCwd } from './cwd.js';

export type ManuscriptFile = {
  path: string;
  type: 'docx' | 'pdf';
};

export async function detectManuscripts(dir: string = getCwd()): Promise<ManuscriptFile[]> {
  const fs = getFsImplementation();
  const manuscripts: ManuscriptFile[] = [];

  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile()) {
        const name = entry.name.toLowerCase();
        if (name.endsWith('.docx')) {
          manuscripts.push({ path: join(dir, entry.name), type: 'docx' });
        } else if (name.endsWith('.pdf')) {
          manuscripts.push({ path: join(dir, entry.name), type: 'pdf' });
        }
      } else if (entry.isDirectory() && entry.name === 'projects') {
        const subManuscripts = await detectManuscripts(join(dir, entry.name));
        manuscripts.push(...subManuscripts);
      }
    }
  } catch (error) {
    // Ignore errors
  }

  return manuscripts;
}

export async function isOllamaRunning(): Promise<boolean> {
  try {
    const response = await fetch('http://localhost:11434/api/tags', {
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function getEnvironmentSummary(cwd: string): Promise<string> {
  const [manuscripts, ollamaOk] = await Promise.all([
    detectManuscripts(cwd),
    isOllamaRunning(),
  ]);

  let summary = "## Manuscript Review Environment Status\n";
  summary += `Ollama Status: ${ollamaOk ? "Connected and Running" : "OFFLINE (Local models will not work)"}\n`;

  if (manuscripts.length > 0) {
    summary += `Manuscripts Found:\n${manuscripts.map(m => `- ${m.path}`).join("\n")}\n`;
  } else {
    summary += "Manuscripts Found: None detected. You should ask the user to provide a path to a manuscript file or add one to the current directory.\n";
  }

  return summary;
}
