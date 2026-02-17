"use client";

/**
 * Lightweight markdown → HTML renderer for LLM-generated text.
 * Handles: **bold**, *italic*, headers, bullet lists, numbered lists, paragraphs.
 * No external dependencies.
 */

function renderMarkdown(text: string): string {
  let html = text
    // Escape any bare HTML
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // Headers
    .replace(
      /^####\s+(.+)$/gm,
      '<h5 class="text-xs font-bold text-[var(--text-primary)] mt-3 mb-1">$1</h5>',
    )
    .replace(
      /^###\s+(.+)$/gm,
      '<h4 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] mt-3 mb-1">$1</h4>',
    )
    .replace(
      /^##\s+(.+)$/gm,
      '<h3 class="text-sm font-bold text-[var(--text-primary)] mt-3 mb-1">$1</h3>',
    )
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-[var(--text-primary)]">$1</strong>')
    // Italic
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>")
    // Inline code
    .replace(
      /`([^`]+)`/g,
      '<code class="px-1 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-primary)] text-xs font-mono">$1</code>',
    )
    // Unordered list items (- or •)
    .replace(/^[-•]\s+(.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    // Numbered list items
    .replace(/^\d+\.\s+(.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');

  // Wrap consecutive <li class="ml-4 list-disc"> in <ul>
  html = html.replace(
    /((?:<li class="ml-4 list-disc">[\s\S]*?<\/li>\s*)+)/g,
    '<ul class="space-y-1 my-2">$1</ul>',
  );
  // Wrap consecutive <li class="ml-4 list-decimal"> in <ol>
  html = html.replace(
    /((?:<li class="ml-4 list-decimal">[\s\S]*?<\/li>\s*)+)/g,
    '<ol class="space-y-1 my-2">$1</ol>',
  );

  // Paragraphs: double newlines → paragraph break
  html = html.replace(/\n\n+/g, '</p><p class="mt-2">');
  // Single newlines → <br/> (but not inside tags)
  html = html.replace(/\n/g, "<br/>");

  return `<p>${html}</p>`;
}

interface MarkdownTextProps {
  text: string;
  className?: string;
}

export function MarkdownText({ text, className }: MarkdownTextProps) {
  return (
    <div
      className={className || "text-sm text-[var(--text-secondary)] leading-relaxed"}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
    />
  );
}
