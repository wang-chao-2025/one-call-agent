(() => {
  const parts = [
    'app.bundle.part01.txt',
    'app.bundle.part02.txt',
    'app.bundle.part03.txt',
    'app.bundle.part04.txt',
    'app.bundle.part05.txt',
    'app.bundle.part06.txt',
  ];

  const currentScript = document.currentScript;
  const baseUrl = currentScript?.src
    ? new URL('.', currentScript.src).href
    : `${window.location.origin}/static/`;

  try {
    let source = '';

    for (const part of parts) {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', new URL(part, baseUrl).href, false);
      xhr.send(null);

      if (!((xhr.status >= 200 && xhr.status < 300) || xhr.status === 0)) {
        throw new Error(`加载前端脚本分片失败: ${part} (${xhr.status})`);
      }

      source += `${xhr.responseText}\n`;
    }

    (0, eval)(source);
  } catch (error) {
    console.error('前端脚本加载失败:', error);
    document.addEventListener('DOMContentLoaded', () => {
      const pre = document.createElement('pre');
      pre.style.cssText = 'padding:16px;color:#b00020;background:#fff3f3;border:1px solid #f3c2c2;border-radius:8px;margin:16px;white-space:pre-wrap;';
      pre.textContent = `前端脚本加载失败: ${error?.message || error}`;
      document.body.prepend(pre);
    });
  }
})();
