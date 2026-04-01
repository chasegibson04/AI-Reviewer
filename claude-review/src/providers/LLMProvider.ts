import OpenAI from 'openai';
import { EventLogger, NetworkEvent } from '../logging/EventLogger';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatOptions {
  model?: string;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}

export class LLMProvider {
  private client: OpenAI;
  private logger: EventLogger;
  private defaultModel: string;

  constructor(apiKey: string, baseURL: string, defaultModel: string, logger: EventLogger) {
    this.client = new OpenAI({ apiKey, baseURL, dangerouslyAllowBrowser: true });
    this.logger = logger;
    this.defaultModel = defaultModel;
  }

  public async chat(messages: ChatMessage[], options: ChatOptions = {}): Promise<string> {
    const startTime = Date.now();
    const model = options.model || this.defaultModel;

    try {
      const response = await this.client.chat.completions.create({
        model,
        messages,
        temperature: options.temperature ?? 0.1,
        max_tokens: options.max_tokens,
      });

      const duration = Date.now() - startTime;
      const content = response.choices[0]?.message?.content || '';

      this.logger.logNetwork({
        destination: this.client.baseURL,
        purpose: 'chat/completions',
        status: 200,
        duration,
        timestamp: Date.now(),
        model
      });

      return content;
    } catch (error: any) {
      const duration = Date.now() - startTime;
      this.logger.logNetwork({
        destination: this.client.baseURL,
        purpose: 'chat/completions',
        status: error.status || 500,
        duration,
        timestamp: Date.now(),
        model
      });
      throw error;
    }
  }

  public async *streamChat(messages: ChatMessage[], options: ChatOptions = {}): AsyncGenerator<string> {
    const startTime = Date.now();
    const model = options.model || this.defaultModel;

    try {
      const stream = await this.client.chat.completions.create({
        model,
        messages,
        temperature: options.temperature ?? 0.1,
        max_tokens: options.max_tokens,
        stream: true,
      });

      let fullContent = '';
      for await (const chunk of stream) {
        const content = chunk.choices[0]?.delta?.content || '';
        fullContent += content;
        yield content;
      }

      const duration = Date.now() - startTime;
      this.logger.logNetwork({
        destination: this.client.baseURL,
        purpose: 'chat/completions (stream)',
        status: 200,
        duration,
        timestamp: Date.now(),
        model
      });
    } catch (error: any) {
      const duration = Date.now() - startTime;
      this.logger.logNetwork({
        destination: this.client.baseURL,
        purpose: 'chat/completions (stream)',
        status: error.status || 500,
        duration,
        timestamp: Date.now(),
        model
      });
      throw error;
    }
  }
}
