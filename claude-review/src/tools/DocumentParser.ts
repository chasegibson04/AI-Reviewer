import fs from 'fs-extra';
import path from 'path';
import pdfParse from 'pdf-parse';
import mammoth from 'mammoth';

export interface ParsedDocument {
  text: string;
  sourceType: 'pdf' | 'docx' | 'txt' | 'unknown';
  metadata?: any;
}

export class DocumentParser {
  static async parse(filePath: string): Promise<ParsedDocument> {
    const ext = path.extname(filePath).toLowerCase();

    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    if (ext === '.pdf') {
      const dataBuffer = fs.readFileSync(filePath);
      const data = await pdfParse(dataBuffer);
      return { text: data.text, sourceType: 'pdf', metadata: data.info };
    } else if (ext === '.docx') {
      const result = await mammoth.extractRawText({ path: filePath });
      return { text: result.value, sourceType: 'docx' };
    } else if (ext === '.txt' || ext === '.md') {
      const text = fs.readFileSync(filePath, 'utf-8');
      return { text, sourceType: 'txt' };
    }

    throw new Error(`Unsupported file type: ${ext}`);
  }
}
