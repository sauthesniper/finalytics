def save_html(page, filename: str):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(page.content())