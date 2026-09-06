from googlesearch import search


PRODUCT_NAME = "Galaxy S24"


def google_search_product(product_name, limit=10):

    query = f"{product_name} official product image"

    print("")
    print("=" * 60)
    print("KHARIDINO GOOGLE SEARCH")
    print("=" * 60)
    print("")
    print("Query:", query)
    print("")
    print("در حال جستجو در Google...")
    print("")

    results = []

    try:

        for url in search(
            query,
            num_results=limit,
            lang="en"
        ):

            results.append(url)

            print(
                f"{len(results)}. {url}"
            )

    except Exception as e:

        print("")
        print("❌ GOOGLE SEARCH ERROR:")
        print(e)
        return []

    print("")
    print("=" * 60)
    print(
        "تعداد نتایج:",
        len(results)
    )
    print("=" * 60)

    return results


if __name__ == "__main__":

    google_search_product(
        PRODUCT_NAME,
        10
    )