# User evaluation for `output/verified_loyalty_analysis_report.html`

## Overall

- URL deeplinks remain the single biggest issue with the report

## URL Citations

- I did some research on URL citations and Gemini 3 Flash. Here are some ideas to try:
    - Rule approach:
        Return only URLs that you have directly fetched and verified.
        - For each result, return:
            - Exact article title
            - Exact canonical URL (copied verbatim from the browser)
            - Publication name
            - Publication date
        - Do not summarize.
        - Do not infer URLs.
        - Do not rewrite URLs.
        - Do not invent URLs.
        - If a URL was not fetched, do not return it.
    - Programmatic approach to elmininate 404 and homepage links:
        - Before passing links to the analyst:
            - Make a HEAD or GET request
            - Confirm status = 200
            - Confirm content-type = text/html
            - Confirm the article title appears in page HTML
            - Capture canonical link tag if present (e.g. <link rel="canonical"> tag and return that exact value.)
    - Force URL Echo validation
        - After listing each URL, repeat it character-for-character on a new line labeled “URL_VERBATIM”.
    - Reinforce the "Real-Time" Context
        - Gemini 3 models sometimes get "stuck" in their training data (which cut off in early 2025). If it thinks it's looking at an old archive, it might hallucinate a URL that used to exist. Remind it:
            - "It is currently February 2026."