import httpx

def fetch_ht_products(upcs: list[str]) -> dict:
    base_url = "https://www.harristeeter.com/atlas/v1/product/v2/products"

    # Construct query string with all UPCs
    query_params = [("filter.verified", "true"), ("projections", "items.full,offers.compact,nutrition.label,variantGroupings.compact")]
    for upc in upcs:
        query_params.append(("filter.gtin13s", upc))

    headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en,en-US;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "referer": "https://www.harristeeter.com/search?query=nutella%20hazelnut%20spread&searchType=previous_searches",
    "sec-ch-ua": "\"Chromium\";v=\"136\", \"Google Chrome\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "device-memory": "8",
    "priority": "u=1, i",
    "x-ab-test": '[{"testVersion":"B","testID":"5388ca","testOrigin":"cb"}]',
    "x-call-origin": "{\"component\":\"internal search\",\"page\":\"internal search\"}",
    "x-facility-id": "09700352",
    "x-geo-location-v1": "{\"id\":\"b9c9c75e-930e-4073-9f2b-cee2aa4fa318\",\"proxyStore\":\"09700819\"}",
    "x-kroger-channel": "WEB",
    "x-laf-object": "[{\"modality\":{\"type\":\"PICKUP\",\"handoffLocation\":{\"storeId\":\"09700352\",\"facilityId\":\"14094\"},\"handoffAddress\":{\"address\":{\"addressLines\":[\"1201 1st St NE\"],\"cityTown\":\"Washington\",\"name\":\"Constitution Square\",\"postalCode\":\"20002\",\"stateProvince\":\"DC\",\"residential\":false,\"countryCode\":\"US\"}},\"location\":{\"lat\":38.9058758,\"lng\":-77.0055935}}},\"sources\":[{\"storeId\":\"09700352\",\"facilityId\":\"14094\"}],\"assortmentKeys\":[\"09700352\"],\"listingKeys\":[\"09700352\"]}]",
    "x-modality": "{\"type\":\"PICKUP\",\"locationId\":\"09700352\"}",
    "x-modality-type": "PICKUP",
    "cookie": (
        "sid=88ae742c-ec21-ebab-b8a4-8825fc7dfbbd; "
        "pid=b8a48825-fc7d-88ae-fbbd-742cec21ebab; "
        "AMCVS_371C27E253DB0F910A490D4E@AdobeOrg=1; "
        "_fbp=fb.1.1747669730365.2063646073; "
        "akaalb_KT_Digital_BannerSites=~op=KT_Digital_BannerSites_KCVG_Weighted:hdc|KT_Digital_BannerSites_KCVG:hdc|KT_Digital_BannerSites_Legacy:kcvg|~rv=70~m=hdc:0|kcvg:0|~os=49d9e32c4b6129ccff2e66f9d0390271~id=4e0b600e5702a2678cbc22403a79fd94; "
        "abTest=3f_8aae36_A|cb_5388ca_B; "
        "origin=lvdc; "
        "AKA_A2=A; "
        "bm_ss=ab8e18ef4e; "
        "ak_bmsc=556C9311540927A76D3468C91408655A~000000000000000000000000000000~YAAQVU5OaIFu58yWAQAAPzGT/xv6Nw1E84jlAKuS8SPoc5y/eur0+0T2FsJV8q6R1q2RmkA78snxZ9Jf++; "
        "OptanonConsent=isGpcEnabled=0&datestamp=Fri+May+23+2025+19%3A56%3A03+GMT-0400+(Eastern+Daylight+Time)&version=202405.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=c58afc2a-16be-444a-8676-ba7e8a0b21c1&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=BG1078%3A1%2CC0004%3A1%2CBG1079%3A1%2CC0001%3A1%2CC0003%3A1%2CC0002%3A1%2CBG1080%3A1%2CC0008%3A1%2CC0009%3A1&AwaitingReconsent=false; "
        "bm_lso=BE5A09725DE39D6D1EE665520DFE1A9D826A5FEA3D6CC87D4ADC25CE65C1FB2E~YAAQVU5OaIRu58yWAQAAPzGT/wOI+Spx+TO48iS4zYv6vJR1gnkoCFDQFguPIKSsrgRdY/gJRJxHFfDMcOUsg4YxdUVHpmI0fFbAw681XAkFaxIyK8abuwjkNIhZNj2nW1614mXLOpbuzBBuzoHcHmtNbrMbrdGVk16U9xN3bZaYJOaLRnSCOf5ESVvg3tjSo1XoVDaFLmHc1pm8E9XjBzaerqf14+H02y3LUUxqCbRevcvpRME+slW7m1utZqT+NFm7xtYNg4w73dn7TdvqejkJrLHJgBUAMCKhjzKaX9KelFtD4g1MSBG/AToLGs3/nI5qbsdYFsi6B5hoGLSY06nofIGYnGMFdQto1RQ0tAKLnf4B0H/bQTSAg6K1EjAfNiQ/gtE6jb3VfUHIq6To2qs06HbLMO5jrQGtpO8CCOEjLMDkf5WGa0BOt3/wK5TqmpUvHezXTfzRXdUClWFKZy66^1748044564091; "
        "bm_mi=CB9AF07EF5E1006F6E688DFF0BADB9A5~YAAQbcgwF6IWNeuWAQAAcYWb/xslqq7ge9sBj+OOG/XYVqZ48/YhRwP7rhtgQlsy0D39LR/sFDdDhf5ryX7jFky0cKSAl6ks1ivTlqL3EOmHOzSSJTt0BEG7nRvFpCKh1rONFhWtzpvZGFW7cYnyU6+e0iLKqnYWDSRfKehuSSllkvv7egfEQAaCae+RQy9FO381fTP4AtqIyGa3g6wcVPaQoN+FadIWxOXXQ5Ug8XoYyF7ju2BfVMeSC7wfuPMnwTSMQlNu02wk/E8DTIhCb3Pt3ZQJ1NlKas1E//lfEWZYW3bYXS7kAyGJmn9PC+Rqc5gHdWItgVY=~1; "
        "bm_so=597754EA81CAD250642DC1BAB1C2A95A410E64DF5B289F3C579BD74BCDC3869D~YAAQbcgwF6QWNeuWAQAAcYWb/wPzViP3Sj/SpbXve4dvpSmt8BtQTZyVgqJ0xss/rawz3iICG+KVeG0rY/tjQmv09CqhY9hRosJqyBBlpR57JAtdhHF+LWg6YHeo2PTEjzN7shT13JgtTII+HXOfHUPkJOTFTtu3VWW35suzjEh28WH3xaX0PabKiIKn23zfa0I/TnzEgHoCmljpq376ZlXKh0sQzrIdnXv6N9vc4vOT47nT0QXE9zSCY9tLX7+Wedhkllp8IzEbjf4N4MYJWt5o+a3g11Y4DQNuXtiqEKslXSfNPITqUPXZsnOWpomADulA5/wVNgMhniFDxhN5p10dYDcA8Pw7mtsJiN+jSVw7xzJ33W+J0sy3f9KWq+kZon4DS8MsPX9vog95iSquIBCFlW7k4A/zYoSq4XpmoXKPKtXTNQBG00uO8g0V3hu6fLVFcE+rzYP7FBUzg0JtZl9F; "
        "bm_sv=077707FCE7DE0D9F86F8496DEB140A12~YAAQbcgwFwcpNeuWAQAA566b/xsa5WcRYG7ie1KiYVUrKuKrJtD9yBuyLlv7QPLMOh+GcV8xWqhN0mV7DNm9r1+ddsfv0zz0oZRfhaCvEVxecOPv35BtwaivMe2jqPbPFsSj9zlXluO9byg4NYjtswSLmAgY/Yj164MsrQt5katdHn4b/Of7P+93p2Y2CqoY9Kch4AxOEsJbXxTmmSXyIYrPAS0pnJgPG4z9DYwX8i54tQAuvUDZ00XublejNGXFKULNO4JTjg==~1; "
        "bm_sz=8D29D2A60985466672C856FB3C5DED62~YAAQbcgwFwgpNeuWAQAA566b/xt7Im5PvosHxUSbLiA3MB36wl7j6tJk/MtucQ0K+tNW5heLA67++ko50Sxz2s+3thKw/qRBFCWAWYwoyfjEPxEyexnQ9LqpUtTECqBUKFU2kYkJD1LO/B7xnLBpXvk/NvcdqQu7rwSHHUpXHdrGmXui7CXdSoyY8Poglm1EkOQ+7ZOqZj5+qRgQQX9Pc2ezHP1BY9hJBxtoHTLb15HCSpdB18yjbq/MDpwQo+27Y3IvpWjPiJ4/3Iv8QQVz68FLcxVrsuA0hsa+NjGgRsKY9Fr4T8mAn2glmD0r3E/FARxLEruYgdruzMHD2IOG9nGemmAvov/QPhXbROgZydc0rvCmx4H+vNgrmnmWU56wSh3qnVa0kW38M0HcUuYQZqNJP62js/mWtgJfRthxfwBA5pTlG7Ub8Ogqb3tg0oeKnpILD3ZeCVZmKQliRVshpWPCILAdtjo==~4534329~3224880"
    )
    }
    

    # cookies = {
    # "sid=88ae742c-ec21-ebab-b8a4-8825fc7dfbbd; "
    # "pid=b8a48825-fc7d-88ae-fbbd-742cec21ebab; "
    # "AMCVS_371C27E253DB0F910A490D4E@AdobeOrg=1; "
    # "_fbp=fb.1.1747669730365.2063646073; "
    # "akaalb_KT_Digital_BannerSites=~op=KT_Digital_BannerSites_KCVG_Weighted:hdc|KT_Digital_BannerSites_KCVG:hdc|KT_Digital_BannerSites_Legacy:kcvg|~rv=70~m=hdc:0|kcvg:0|~os=49d9e32c4b6129ccff2e66f9d0390271~id=4e0b600e5702a2678cbc22403a79fd94; "
    # "abTest=3f_8aae36_A|cb_5388ca_B; "
    # "origin=lvdc; "
    # "AKA_A2=A; "
    # "bm_ss=ab8e18ef4e; "
    # "ak_bmsc=556C9311540927A76D3468C91408655A~000000000000000000000000000000~YAAQVU5OaIFu58yWAQAAPzGT/...; "
    # "OptanonConsent=isGpcEnabled=0&datestamp=...; "
    # "bm_lso=BE5A09725DE39D6D1EE665520DFE1A9D826A5FEA3D6CC87D4ADC25CE65C1FB2E~YAAQVU5OaIRu58yWAQAAPzGT/...; "
    # "bm_mi=CB9AF07EF5E1006F6E688DFF0BADB9A5~YAAQbcgwF6IWNeuWAQAAcYWb/...; "
    # "bm_so=597754EA81CAD250642DC1BAB1C2A95A410E64DF5B289F3C579BD74BCDC3869D~YAAQbcgwF6QWNeuWAQAAcYWb/...; "
    # "AMCV_371C27E253DB0F910A490D4E@AdobeOrg=179643557|MCIDTS|20232|MCMID|14252701268112830226993937071550909039|...; "
    # "x-active-modality={\"type\":\"PICKUP\",\"locationId\":\"09700352\",\"source\":\"FALLBACK_ACTIVE_MODALITY_COOKIE\",\"createdDate\":1747856531832}; "
    # "_abck=CC744AC737519E3B33F706D6115EA579~-1~YAAQbcgwFwUpNeuWAQAA566b/...; "
    # "bm_s=YAAQbcgwFwYpNeuWAQAA566b/...; "
    # "bm_sv=077707FCE7DE0D9F86F8496DEB140A12~YAAQbcgwFwcpNeuWAQAA566b/...; "
    # "bm_sz=8D29D2A60985466672C856FB3C5DED62~YAAQbcgwFwgpNeuWAQAA566b/..."
    # }

    with httpx.Client(http2=False, headers=headers, timeout=15) as client:
        response = client.get(base_url, params=query_params)
        response.raise_for_status()
        return response.json()

# Example use
upc_list = ["0000980089500", "0000980089220", "0007203670809"]
data = fetch_ht_products(upc_list)

# Print product info
for product in data.get("data", {}).get("products", []):
    print({
        "upc": product.get("gtin13"),
        "name": product.get("description"),
        "brand": product.get("brandName"),
        "price": product.get("offers", {}).get("price", {}).get("price")
    })
