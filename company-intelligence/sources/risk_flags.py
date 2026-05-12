def build_risk_flags(
    monitor_data,
    bpi_data
):

    flags = {

        "insolvency": False,

        "has_monitorul_mentions": False,

        "high_activity_company": False,

        "reorganization": False,

        "bankruptcy": False,
    }

    #
    # BPI
    #
    bulletins = (
        bpi_data
        .get("bulletins", [])
    )

    if bulletins:

        flags["insolvency"] = True

    #
    # monitor
    #
    publications = (
        monitor_data
        .get("publications", [])
    )

    if publications:

        flags["has_monitorul_mentions"] = True

    #
    # lots of events
    #
    if len(publications) >= 10:

        flags["high_activity_company"] = True

    #
    # keyword detection
    #
    text_blob = " ".join(

        str(x)

        for x in bulletins
    ).lower()

    if "reorganiz" in text_blob:

        flags["reorganization"] = True

    if "faliment" in text_blob:

        flags["bankruptcy"] = True

    return flags