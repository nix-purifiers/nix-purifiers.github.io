/* Copy the source text, independent of syntax highlighting and visual wrapping. */
for (const [index, pre] of [...document.querySelectorAll('main pre')].entries()) {
  const code = pre.querySelector('code') || pre;
  const source = code.textContent;
  const block = document.createElement('div');
  block.className = 'code-block';
  pre.before(block);
  block.append(pre);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copy-code';
  button.textContent = 'Copy';
  button.setAttribute('aria-label', `Copy code example ${index + 1}`);
  const status = document.createElement('span');
  status.className = 'copy-status';
  status.setAttribute('role', 'status');
  block.append(button, status);
  let timer;
  button.addEventListener('click', async () => {
    clearTimeout(timer);
    try {
      await navigator.clipboard.writeText(source);
      button.textContent = 'Copied';
      status.textContent = 'Code copied to clipboard.';
    } catch {
      // Let the reader copy the selected source when clipboard access is denied.
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = 'Select & copy';
      status.textContent = 'Clipboard access was denied. Code selected; use your copy command.';
    }
    timer = setTimeout(() => {
      button.textContent = 'Copy';
      status.textContent = '';
    }, 2500);
  });
}
