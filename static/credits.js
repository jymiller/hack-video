/* Credits strip. Marks are authored here rather than scraped — several vendors
   block their logo assets (403/404). Drop official files in /logos and swap the
   `svg` field for <img src="/logos/x.svg"> if you want exact trademarks. */
(function () {
  const M = {
    twelvelabs: {
      name: 'TwelveLabs', color: '#3fd0c0', url: 'https://twelvelabs.io',
      note: 'video understanding — Marengo &amp; Pegasus',
      svg: `<rect x="1" y="1" width="22" height="22" rx="6" fill="none" stroke="currentColor" stroke-width="1.6"/>
            <text x="12" y="16.5" font-size="10" font-weight="700" text-anchor="middle" fill="currentColor">12</text>`,
    },
    archive: {
      name: 'Internet Archive', color: '#d4a24a', url: 'https://archive.org',
      note: 'a free library of the public record',
      svg: `<path d="M2 21h20M4 21V10M8 21V10M12 21V10M16 21V10M20 21V10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            <path d="M12 2 22 8H2z" fill="currentColor"/>`,
    },
    you: {
      name: 'You.com', color: '#8b7cf6', url: 'https://you.com',
      note: 'search and deep research API',
      svg: `<circle cx="12" cy="12" r="10.2" fill="none" stroke="currentColor" stroke-width="1.6"/>
            <path d="M7 8l5 6 5-6M12 14v4" stroke="currentColor" stroke-width="1.9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,
    },
    neo4j: {
      name: 'Neo4j', color: '#4a9fe8', url: 'https://neo4j.com',
      note: 'the graph the findings are written into',
      svg: `<circle cx="6" cy="7" r="2.6" fill="currentColor"/><circle cx="18" cy="5" r="2.2" fill="currentColor"/>
            <circle cx="17" cy="17" r="2.9" fill="currentColor"/><circle cx="7" cy="18" r="2.1" fill="currentColor"/>
            <path d="M6 7l12-2M6 7l11 10M7 18l10-1M6 7L7 18" stroke="currentColor" stroke-width="1.2" opacity=".65"/>`,
    },
    ffmpeg: {
      name: 'FFmpeg', color: '#7bc86c', url: 'https://ffmpeg.org',
      note: 'open source — durations and media probing',
      svg: `<path d="M4 4l14 8-14 8z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
    },
    ytdlp: {
      name: 'yt-dlp', color: '#e8886c', url: 'https://github.com/yt-dlp/yt-dlp',
      note: 'open source — corpus retrieval',
      svg: `<rect x="1.5" y="4.5" width="21" height="15" rx="4" fill="none" stroke="currentColor" stroke-width="1.7"/>
            <path d="M10 9l5.5 3.5L10 16z" fill="currentColor"/>`,
    },
    fastapi: {
      name: 'FastAPI', color: '#3fd0c0', url: 'https://fastapi.tiangolo.com',
      note: 'open source — the proxy behind these pages',
      svg: `<circle cx="12" cy="12" r="10.2" fill="none" stroke="currentColor" stroke-width="1.6"/>
            <path d="M13 4l-6 9h4l-1 7 6-9h-4z" fill="currentColor"/>`,
    },
  };

  function chip(k, big) {
    const m = M[k];
    if (!m) return '';
    return `<a class="credit${big ? ' big' : ''}" href="${m.url}" target="_blank"
              style="--c:${m.color}" title="${m.name}">
        <svg viewBox="0 0 24 24" width="${big ? 26 : 18}" height="${big ? 26 : 18}">${m.svg}</svg>
        <span class="cn">${m.name}</span>${big ? `<span class="cnote">${m.note}</span>` : ''}
      </a>`;
  }

  window.renderCredits = function (primary, others) {
    const f = document.createElement('footer');
    f.innerHTML = `<div class="cgroup">${(primary || []).map(k => chip(k, true)).join('')}</div>
      <div class="cgroup right"><span class="cthanks">built with</span>
        ${(others || []).map(k => chip(k, false)).join('')}</div>`;
    document.body.appendChild(f);
  };
})();
