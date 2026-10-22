"""
Zero-Zadig Automatic Plug-and-Play Driver Installer for DJI Controllers on Windows.
- Embeds the signed WinUSB driver for DJI RC Pro Enterprise (VID_2CA3&PID_1021&MI_00)
  and the official DJI Virtual COM driver for DJI RC-N1 / Air 2S (VID_2CA3&PID_001F).
- Also binds Windows built-in WinUSB (USB\\MS_COMP_WINUSB) to any other DJI BULK interface
  (RM330, RC 2, RC-N2, RC-N3, etc.) and fixes the Windows WinUSB Code 31 Registry bug
  (duplicate DeviceInterfaceGUID + DeviceInterfaceGUIDs).
"""
import base64
import logging
import os
import pathlib
import subprocess
import time
import zlib

logger = logging.getLogger(__name__)

DRIVER_BLOBS = {'BULK_Interface_(Interface_0).cat': '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', 'bulk_interface_(interface_0).inf': 'eNrdV21PG0cQns+V8h9WVly1ku1wmJgimigYAqEhVkQIfEiRZfwWFNdGPucFRf3rbZ+Z2b3dPR9wplEVVaeD29mZZ153Zv33X9tkqE1v6YheUpcOaUoLGtKcRtSjPr669FMhdY1+pgZdYmdED+gHYpxdmtEVXYPvksb0HjIG0n1wGlqHRIK3Ll/r1ATtNZAYly3o4asHyQFWvwJFd56B9gH/Z6JrSE8F8YA6sNjA5gNgHAGfLXhHbyAzF5vGlNK5UPcg9Qk0troDtD9E3xO8lcxvU+ChKfTbiN8VQT7Fegp7Z9jPI+/Rb5A2dAJaH5GYgmuCd4zoaJwaVBMPFkBoWMQ3oH8E2re0VflTie4Ej4Ftl1h/sDrD+BxiZeRRnadC6SJbu7SDjP2IaCslkRwmoLwChathrQDvADYrpuJ9hRcJ5DZBew5MroYmVvtAr9OGfG/haweUTezXwbcP/i38XcP+pny16TH9abVp3k/F7xRaZ/D13MaSa3AqdcUxHUaePaQzqRPO3mdIGsT7BFRF3UWceqCmVsZEsm+B3Y78zEsdQOOlVLKT+kq/4LnA/hCeNOFTHV70QEvE8y1kjaNxAbwmJOvY2wBthP0muDjWLdBb8Jx1vYZHM9E/EN9jCyegX8CvAf4723q2ArgG90GfZLV1/9PfF1TNOp+7T8J1Glj0RKqwRY+kXh7ZLrAutd8CQoJ3E19cPw3xkb19HOTWRzWuY46hZnoHfg4kw2OrUXO7nCePdSzcXktZCdX4AtE6hg/8rOHlmphm/qdioQHWUKKiqzZqgutpEKCnNjse7xB0rmH+1k7pbXwFpClQNAuuqufWpmphP6raiGhFsAUXkX/dyPOanIIvyEDLfjMKV91Gtp6DwmtvVznsRoDtLC7qzc5ilermsl7Ldn7PyXOfqd7TKu/l92eZi/d/YVmxvGpmWh+rj1LBqu+z2KuehHeBDjiG4EuDLnAGhE7k2116G/YE+dNSbInXcZM92iFitOVOwWf5i3Qi/3CnCnm6OZTY4uJ+cruMu6XwTL6SbnMdzH7f00NEg95g0DMYdYq/OtV9By7uubd3XHcDCS09gS1XkR2J5dK72iLH4biawvUcHHPpRrvS0xaymixhhRrb4iVjX1uuqtheRe3GpyMFR1qihs6Q+ZGN8ks556MbKsHXZy2oDK6lbsk8F2XW6TySUz+3vsU3FhcPzkdSwqcX0BvOvuNg9iklPuX5+e3uZV5TB3aUkznPbvs74J7JDYTPeU/06t2bV6YkngFlJjU7lvmlM7Mvk9JXtLd0Ff/y07qcVGo7QZJ1gVqubzrOaolc+anXkHMQ72sVFOXSn6abpLqRhN7y9PeXu9+ldyIsS5TzyE/M/5dXbtre5dV2dEMt40m+Fm+SasrM8ZMorMKK7WbFssqbSB8Z2Ml/G3/FIvoOVsy3nuFVSnm9HH31fRVNyr+Kr96yPdG5sJNkYXssT1ifv1Wsd9057MzhL3X3ezrN5rbTkmQzrOiXffVOPG9DI7o5rxJJZ33NIqwe2SKEslbnb9b3s9yj/BvrY5TyHsQ38G36B3ue+Vg=', 'dji_vcom_driver11.inf': 'eNrtmG1v2joUx98j8R0sNPbiKmTOQ4Gq8ouShI3d0iLo2KStmjziIq8hZnbSDV3d736Pk8Cl925rXI1pk5o3iZ2fz/nHD+fEPkHNxgmKP3K4NRvNxts5k4qL9ArqZ3yZ0iyXjLSevOZpLD4rdH75pAWvgoQqRSZCZqoqPM95TP7yQ68bHff6nchzjzqOE0SdwTBwOriPsTuIHOw5/b+h/USKWx4zSdrhy1EbKkLJb5kE54jgo2eu/8zFrmMh3+7bPRuDD5rRRCyHPGEE1MYFbi9oVoge0zS/pgutVWrlhVUSslu+YGdcZVaa0VXc9TV80vmhl+4+VHpCCbg6gAP4wH8/5ar8unlwMW4jRN5MfGyhV7PBu/kofD8cDvHTCTxgjPtPxyO4o9o8qos6w8K0/13eDU49Eyl3eFQX3UqphTsYHxW4i+ryXRPeBz2GvFvydfFjI9zpGuCgvewcpy5uaL1nhvfN8GMz7adm1gdmeFDgXl08LJdHXTwyEONh7BmsEMD9GnjvqLtdqj0zvG8ixunj+/H9EHZcJy79Tw2uz6Pa6F0pk+nF5dm90cbB+yMbRoNXz+u28U38uA/w4z7Aj/cAP97Oz17Os6v0fcDc9+ukvh+Y+X7u2njY0vhtczZ6TNqPSfsxad+TtB8zn3nmO8QOdZQq2EAnNIO9/WG2qDORywULubpR53TF1NV/a/Xevaod0hs2FjFbBWK90fUzttDKrqrNrsp4WkgNuVR6Q/+tBsSBPg7ZNc2TTDcDHhGkK8GO7mrdmKeLJI8ZWcWrxfqTzdPrZmNrR5FvmW42TuN4ypbFiNnlM9rZrSq0+Rd/Ti0LflbOBI2ZtKw/0uyGyXT75vxyPClPNywrVx8Uk7baqO3bKM1XEynWE7pkynMtqzVWxbGKHSeJNWOS00SXt8z24KS1JwUo/adUdBTIqoqkdGYh/AWXl2uhUkhFlJ29X6MtwFitE7rRY0ja4XQ0j6b2bB7oQ5qKutysGYGoPcuozIoCRM1ISiEDkWZSJMXLkh3AQMoNaTtu+92drz/MNJ9lkqdLBDOCp1yPojrQZC/8FD0OCxxVF0Gt+CPv8DQVt8X0VQjmnt0CaNePGtJNIAKgOZdZThMEoaEamVZhT8eKyt5X0JLZBaI7lC4PhUQwTTKxEEnJ7gLQV9mQfciXAP4D0yf7pA==', 'djidriver.cat': 'eNrtWgk4lN3bf2Yx9p1SsqYSMueZxdpiTci+JTS2wZBtjCUUM5XSIlKSkiWFUlJEi1AoodKmTaWyvS2kJKl8z6BSr+qd7/3e6/9e/+vzXM/MWe7zm/vc59zLuR3A0iDjeFUSliQMCqK40dksjdmApaGIRqFgYSCI43VPWIKiYrBoFBcEWGKncLyqOBQWxdLkQ2WzxA4hTQeBAI5vvFEAhcKKdKZ85lOMuaaXWHFtXeaRgdKpggQYkAmaQJNAJhGWA6EJ5Bg2KqoJeSWw8uG7zjUq7z1ezIWfdou2Rb2MJ3f29hoza6zM9lu0+1KCRjCzF4h8G4zGwGgWBEgTWlDwbKAkKwBZQXaQPsRAHjoaK4KCUFghAqQDwRCA1JEXgoDld6P0wEJZHmgxRINWQtTxEWrekD/SQIEiIC8oGApESt4QHWmJgKjIN4w86kgtCPJh4zl8xUOjsLAJMJ7AKRo1LRcdDwH4B3n+fsaAWYKVONGZdvtwr8OtD8aUgqRLS4/MjeeLgJnp/1ZRZLNEUgFLZBtg7pgIjGWuB0yW7HSEnXDIE8GgQWHIQ0PwgiB5yBQyGv+xFWSIABEhEvJojrJJQT7HaiSkRoK0kFcbKQGkpA1pQGx6yigT7JI28rJLAHk1kBpxvFUbGU9kT3fhd1wBoC4rAhkgPAUhc0KmPIETibFpT5wqMl7ru/EqQFlWDHJARn8hCYM8oJXjCAKL2RWkicoeqfPdSDWgIjsFMkK6vBASD2SkB7JIoyjjo/nskcbwsbEs1PfSZKHWIW3xslj2Ao/Ts1Ah7CWCR2WjBn0rU6BliCxIP7TZIksBT0o3eR+7jfALesIk9MRf0BMnoSf9gn4y/sm/oP+xD0b2wJKfznjyXkdkq05Oz+5B1mXFd6tiDSwRlVsCObF3ETJBzfGV0QpH9oAn5IrgsPcTBZGVF7LcRGg2FDLewsYnIu/sUdWgjO703+Jr/B18wu/xyZzhEzjln/R38P8C/0TO8GFO+Sf8Hfy/wD/8c3zNUfv2DR+MPto/8m/7Hb4RMPgOH3wx8H8VX+t3PCOmllOetSbwDH6Pr/UzfJ/RB/xeJr/G50BnkQVCuAec4Wv8Hfn8BXwyp/ianOGTOJEPGMXkCJ/IKT6RM3wOdBaM6iyVE50l/EpnJ8f35mz/A07xvSbgE3+HD/9KfyfH9+REPvDP9fdn+B6c4Wtyij/RPsC/x9fgFF+LM/7JnOJrcoZP4hRfgzN8Iqf4ZM7kz4H+kv43/MOc4X/vX/4CPuAUn/Ajvut3+JZgqSzfV3xtTtFhTtC1OIt3wJ9l/yt0TU7RyZygc6y3Pj/6Fevv0A2A3gR08s8jqcnQxyOpX/HLoZ5OEkf9Cp3IWRTFoTQIP5PGz2K030oD5jTq+1Ea2SzBm4CFiwUsrHc2Bo1Co8XZztBQx09qHzF57gaI/WfIztCM58JQ/FwQYCbB/IAXh3HA4sTRDnawOBBlV3jE+Zw8wvxoQb6M4CBYBAixG7nFuW2p3oHBQd6wLJjBbuETl7SgedGDw4J9GPKGwfSQYLoHg4aM0AIa7H6MOP5bvxMtyDs4Mkze3o9G95a39qAzViFjAkOCg6hByGh9eQKASUB2qiDyTYDJBAKBTNBazk6uwQRAGK8CZso/wrAu0B5jmPBnhpd40L0jPejUUW4Rck/aShrCu3W450pamB+VDlgoxYlyRXFBGBZKmJ3T4EOzUCiovHnmYLIwucD/kMQZkulFhmryU0rJzltTVwjN8YvL405XiSWFGeiHleTIRhY81lA4tnnFwkjtd/zEEAl4hrhvhgHURlq2fMT5ZvUi84eNm82yC0UE0TSLipKDWU2J9/0OZAluurdsS7Tjbc1XVfadIzk3V4+k1dJj4ncsj7TwyDzYUFraliGhelRfnH/H60zXA0INT2UsLG9isVFMc8+nNVb8dc+sDx1x3q5eo6N6bECFvK8HL0k5UCmpKg/q7/t98Ina2fx5xonDZror+wWids1wS1G2a06JcKInBW6NvbRssK9jLXZbst31BQ+PnF8oWnOjb1qBTcEVcxOiwQLSyaBPCq8kp6ExyM7eP5YGvQTUEEHLzMLOAjO/qgMfhgvH/62MwvEgFS4ubgwGyLCphbBTsBLDYeQ3Cx137Ehp7jLYcO24hmf30dOIkiLdolhTYJJnDAzhuWAOexn5xeW/LaNVCHVskcOQJaPSGcHytjSvYHgKkGCTcokLEogEmKSpStIgwhraQI6NOBMrBabES1zS2ZtvdmFm/6w1p+4dnmsnZA9dyAEMNoEcNhAEAFq2bzY1wcuPwQjRweMjIyPVA7/8rLpXcCA+JIAWHBKG96Kv/KYHswhgfGMhpVFdQL5HtQH5/qoP7LI+8sHWCXVkPGAyvwgFhcKGgzAQ+qUO0AnU33KAzDvsb/LAAALsmYujUCNYNGJzvrckGBYaBekkSRZruNdGy/QaYpL932xeeTAlQW+PldHzbpGgKyFyQVAX6bMM//HkFtOVi6au3yeX9fqNSHzb5k+qZShtx/Nvsz6HpfjY9y0ln3qEPx7rkC/z5k57v836G+mHXyqZGzyJ1K8uabCr0a4WrUD1CcX/sVueKwe43XZplCes4hfc4BUQfn14m6Hk4uZk/2MHrNfmBs42vaO4Qdq/qKX0zkXLXA0a5tUJqS5W4ElLnfVbvSKv4jM8tync7qXOScPUbJ11g9qmKdA73dh29au6xP1wrkIDb8Gx6yhB7sQQ3y3eWz2nxDs+LQ+fubBIvkOgWrvAGWJkeUbr70t0/tgv+zHxXoSBB/czgkfTg6OnbztXZFS1uU2P6rmplbA5a2BLkU1E5aP3l9pEoaRW9eumZ1ZHFTvswTrKBhgd6loXILJgXkX10+kUHymboejG7PAYk6UzDpleTXqZ8FAyT3SDYZ7UyVLJrkg0NV76gIhH2Q2FWS9dcp7Edetc3DnUlJBoWmLh/NzK2dfrXgp6qPPotp55nTJ+xb6FuMfnDKxcmQ9e3GxJ3qnjo7VUl/J0UYyeCi/p/LlPZjbH+9cL9a2QDK5tXyx0GO/7tLFh9/0IOaddApeHa5P1enanUexwNQMNAu30O4n7D3m9sFZxR/OrxFiNOKpm1tXxJeHO2vZZ9X22c0h50llOsNX28bBlZgAWtzVgcWlN8D+CNEG3qNRrEY9G/Y/gn/zPxn/EnBMAGDPnc7/12wYHI0SIItB8aF4eDKq8fjjDL5jONuXIDgdszwOTYIB4HkCECZpsz6M9ViWxq/8+V8lC/9ntoNluB424HUQbGymyh23e3ljtMe/6tIzKWZ92uYY3N808ttuh/1Q8RsM/OL5eoOz0/DnGWJxkwBGhh2tMjmphwgIWKIsLKqnhtaWW5C9ewVNYa+fesAXsr1/tpbD4MU8qvmLnruC5I6vuJO3SvkTc7yQL6BKvyqPjRpzvk6+F9zQcp2c61jSWq5Vf3COLD8h8bKoj/Vb7RmUBfz5tt4v4DEtfXs2j2QWzqctPxx05Y3o5EeerWNe9XXraNnSonEsNQwlX1B2tXOi3Ns/gLF5pDfN13BzvbSG+fhfow7TWjj4hNUXiM+mL0q2zLPAfI4bh2P70rCQ5/93uh6teE4QvfyIuyXR2XXbkyYK5UcqAcYls2d+bJrX8vnvBua5PGUVD1QuerrY0u8pPfaSQF/pMUXFtv527bZINU4ec/UfPx5rwx+vP4wzVUoVulHsW284hhy26L5pnOnTm6aNFO+8O3UztDrlb5MIjYAqHUert1Pbwhi8xIprujgSKosybIo6O6koPttTuKZXc77HpTm1vR7PR8BFGNyY3kFadmh9RNeXuKpvjBSLJqAcbNBbaHA6922K5M6nzjsubQnLIBl7dLQ59t8LIoRKfA4QcJU8EkKoYXK+ydQPfB8FiT0zemneVmwo+pzbmzFyXF+Py+sknb9qVE3LSLll+feGKUcEF2o19n58d9D3Fvzj0c/SacPGFTu2O1plf3G4h4nYPAJGv/9mURGER/YQmuNZJ/Zw3u1se6wZcAA6HRYoQsMEJjGMsXbsahQL6YNEXL4RGTSH+zgsZBXuF4W2pIcFhNEYwfZW6HyMQTPvKlgQaK4AExGP/PjOE9AE/mwFhLJvZBCD81fdwAQzy9Z2fvvXOsXFbd66rp1/Lgh3JLq1XMqRqgeOYn7YCFsA82zTbJMF4nD/Enf6Zv1EnHUIP9g73GvOUiLlAjAViIyhs6zAPaMwjEEc98fIJjhiJ4YHZBEe88Fci+OaFf4LNmMynppVd0IX7YwJy5JzbGGqa3iVns1OH3hBNeobc+mUS3zrte7pIZL+ztRSXrsRc/ZP5Qi7M3KbKdQY1teda1p2vrRTYYnK2cmPC8HKetKNq+EdVqT77VeUvr9tEM56zKGwmIdV/Zs/Ip7tSL6+MVAboh2112vu+NNA0natzP7mwb01QQnVAAY/vrOLq3Vvu5+Ms9FKlNhc6d+6WOCU2lWlU5HThaNLRHTGNuklt0aWhLqdVL1y8tn6muaZY5AEzfNz0cq9TRs4vt4OmZ7G828VE5WwHZNEpea2tHdviTUak9sS17MWFPngTMS0y+ZaK8NmVYrV1AvI+A0J469Q7l4fjOhxf8t7Jtyu5qEKLetBH6TKXP1nsVdZe4hpvuTe6UMZiUHlxlAJupwWhzd3g2cnptf2LNR6Sw9A1ZR2UU6rOxtHbDVtre7zaNLZFXFS+XGAk3U2Y7tPcscTVjM9ddfF2nHta+oO7xFaFyLiNgUUm9Hu5i4MOe/upXrdMHyY3xb1YJB4o2nE/8mXNhTVy/mYS70vzFepDE3xDmu9M2+8ml70nI7bOzYKexOCOy7eAPrb5KYlFqjiEz2kuVJNJip32iqaWxZhFZPHc12qKvWi1UifgvKZoFP2zg7O3O3Gh+qPaeV1qrcN8rFnBFa0C6w601zKCVHYS9mV/bi6V2nZD9wjheElGRSCX4fCIoDDMkgwHLMlQNKJvzIP/Oi/001PmhHsA2cxyIPV1Z/NiYP4JtywQxr7dI+CHhSbctkCjJAH+2zgsrIiVT+C7uUc4L/CcvJ4thvBmqWNq6EiHrcG5FXJbMyt87WhMsHTCcAF4IZifLRQvgFiV5ZA8csw2g0xzVOKV2WoaNqmeUoPmhYfhI8en/oN/xbJQUJR1OGyv7ZnWpXzfz1mKcmf5pqXAf2OzuPjczD+4P1YDfS6bHOvtCQtrtm6KSm/OUpE5eu1MWrnq0IVEVqizeEiWwwmXPVpbGWrXb63ZEGuva8u9o+H49kCjkhd2F6rfO3psnRk65NqH9q/oD3Ou0Z39WqeiTLrcwPZcVrS6lomJtDp8a9vBlCqM+YXB6JXOVn4b6hdF0Ay6uJ6XFGq+CDzxIYyy2X31hvYDmZsfkq6rdMZeuiPA4CqtKCkTer0Rl58+Z/hGWm6IXnhf9B278M1vTi+IXKYasaWzRN73HfFgY8SNI65naYAShttqeEadkolmPB7yOWT2+jV6x2L661dRZknvjqJzWGIdgCXW/lXMGAwKZom1IG3N392zETuHNJ1GozCT3LNB2eD4vyyrCAqbzULpIbKdj3RoIft8HHqdMx8GNcmlksubBrSPv9P/bPDsRZv9gp32Z2CUQCn32urVNvpVPIMX7qNx7kfTMh8xpMSRs8uXmzkaBFidSEbCOGw8GvU2m3ktj9kMmJf/EWViH21HT6EzvvXrB1LpSNg54TTKvr8yRiZj7+exkooomp2dvLGdpQ7RwMBonjGRqDXPWFsf/gKHmQhnTwukzrNjeASGyNtR6RE0L2o2SwiRH/Y1YGHufou/UVbe6uHvojHL17IVE2X1Y/wd+48IYHxmGHGZSTm2HrMdYDzZA8MEWIugAQjskJu9ZPB49b9qfX6bJdovEVnm/c5P+YX0s0+1vcNLZGYXb7pDgUfUZm+gzyrjl18VYBtRYvq4RFPBjDvaPNQrswHqV1JqCcrzT58nbfp4QPDtwPzNHz4KbRCqj9QQetPGa7i2r3bnKop+XnH+6szVi+x7tya1DDfwn4GWmuRzFQ2vkWg1mBuS1H5rtaVjYWmJLOPBRofCdFxD2DWripEzB9Y32e4oD0Al+li5Yp1uhV0rKxJyLVyIrmAKmAtx2/Dz7GFyrSQ1cc1s+Tzd3HSZ8syYwlukK/nnCt6hjuB7roU63VraorF6mJgXa8QjXHei7HlNfa3kS9Jd0d4AY+aCijzqwRUyKG6heet8b8w6Pv/IIv9PX8JVaUQiUycEp0lbX7VOwYmscUitIp/3fg1T+rOzv4/+vHRcN8HJbwxjYhdL1xH9lq8PdPi70R+yfsjqIRt1PELTnAfg/6vo7yfYP+ZXxMfyZAKA72s6jOdPASKyb+bDzw7PcH1GEIq+3BIzf08uk7JrHTzdyyAgL+j+88f4oPPPcfotsrHJ054sX6GXQeg+u9vs7K5EpXf7PCV1a2weUgRC4npEU3DqUjYRmdN4Fl2k3kv4gHpICF4qK3xPh5JuG5yXoae29tPGbjPrITSkpTz3xR539cqjb3BBRoqyWYmvzHX2ax5dVaXFG2Hd0xw4WNd5Sacyh/70Qs1NO16bffLFjHeNDdgVAdjBqpM+Wg025djbVcUnOgeqipxrugbCG/UtjPNcXEYCPt8uqHtJ2vhcK+r8+UbuDZDcaZuYjCtcui4jC9ZeOV1T/+Tg5bO1HrVCAvsSMK9kPBrm8EVK3yxq6zgFWLhQxPA5jxk9Pg9epspoFIL+l+caANBkJ7qJGmQy2/CRx6okdvU/bJZ/Z6kKZQTPRopu0pF/8VF818CHONqOAIa9yK0DfBBr/fDLWD9zNUrdhQ6P8xHlC31UXfok7eZgYTl96ek7Za7wiifFegDnEmAk/Np94zp7Q4FWiwotnhMGbalFt8OA02zWfmPBa38MmDCbq5TcCcvcF/cvM0kgrJNlePimUJj2JVdTl26vqT3o1uIhHqRcP30oIf7MI4+Pi2vmyCj5itGnK2wqNvdOtPYscfsUKbegzym8qHKTgYWeTYvwXtxC37gBn2pMmtGa3mvmn4I6Mi6XFPRHq/DBffcscSknN/KQu6NmHOvZ3Ty/C290Ov/tA+/KPFSNPG9qVPPHs9UNRm4rpuxFcVkpWnyxVJ2IRJ788mA9qWn6/yPvxCMvM3s0z8CeJnMnYG4HzG1f5aOOAUwmWDAhxwD/9NeszU3x3uwEg6G1Hd6b6uMRvpIxmmHQ+zocDUiyBHkZaClEhXxHL65SIGsoGPmmQV7QKqRmBzFGb6lSoUDkDUJK6vIyk53KuTs32gg+qX+cvogZilmQuT9HIfjE84NNA/C5q1xPCj9/cAqcBk6cr/Np8H800NUXVXmxYN+sp0NnXwbYO/Go2rCMxIZP2W1peusutimiSU9Pf88D16kjrkMrppLTlRzNGb0GIpeKq+Lq4/o1Vy9fNKN/9yqzFFuoWEt46gB+FZN6t7As4NnFK+8uR0PB5sBISXH+1ZeYA2nbnOeePfkJ2x6SRTCb88mhGP/5ZEcS8YwnJeO+k17P6yu7fZK3jPh7xrXVmfGnzH6i/WKaGRJFxCgEXti7P3f+h7jVaf7JUQcDr7fvHZL5qHVnx9v6A3xpCXmV+6YfxRqsrSiL36OoJV82q8P7xeDbqjVezrOEo9W1nSJyQw/hNgknTjntkS/amHFHyCQjvu5ac/613tVr+9p1Q3kfuTHSFXk87h2zlg2ufN0OPeqCufNSdQapJlHd7wuWHB58SF/jERAcWchszOct0j7zor7xDquU3izztmI9SjZ+WDpRxV77uMu9S4IOu6M3hOnydKbP+2PrY6K62NyBarz9HIXBS0WW95QrSgrvpx3PN8htuDpN3+JxwpBKxn5RH3DjDINg/sgrZmD3Jrz0RYVi57KjD4zm77IObc25XufwlPbQqablIaj+1NRpMSxY5WbVkyk7TQt/9uoyLvVewWxr8r1e3jkzbp1YQ5blOX1P4/4NyraHjI2mYjks9BXAQmuOnsrf5/z3HSdyZ/IhU+PGcakKYdDTMZJQt6LAk0PXuXX2bmndYBu5Ym6UyuHubOZawIzPW/Mf9lcT9JOLC0JzQc+cK9uAopTwl/MfTCIRiJrLvzZojTeASMS4fD1sYlEwHrFMfOMAbEvOh3yg0YqRaMT6co+WRZPHCFyE3dgEGhOGo2FlMPtr+oJ9ekVn8wEe9jAMd458zpcyKiH7B5YxTCZiembryxDeqesKJr1MrybENIk3Xm7XEn3hcArcsK4rOYd1w+XMM+Zh3upYkdukUFR1rvjsTqaqksuc152RDY4LBih/4AofVVX+0W6zJzjsSfsV6xFLQvXIJcr9FBXqoiBIjLCtzkhK/1xXeemF7s5GX36HwIGXkXebW94nBl4+cfpqDszCCCJnR97RHZ36n13Rnx5dJyaVWCgzMH1iVknwu5zCnzJHDUXvryjnpWxFr/UqSRdduZVSN/VQvad6raxqwrFVlMO5gPlhAgAaDzP/AMwuwHwGmJVYech3tsg71rK86nq6QqAUPdrw6qH3qwLBVpG6+hqoTBMNmOn/AlWYXHDI5JknpG2PeeVPU5LceEv4TSKjdX4kOSFLPtSmCzuIv0oT/sHHsRNdccnXD9pEkmJmvq9zgz7XnL4rfoNUkZH1mXcm78lUVQoBe0XN7dXy2Wd813VEDZovY6hU5ni6S+7GONXraTfrpdIJ74iQiktlFy6jfWqYcb2acg+qtXuVuHecjb+egZJ+X4106KmTchcjmiOzfKN0Y5K51s3dIzaYdm6z89N4x9rUqzeL17Bo2O0PVghsSlN/c/BqVu+q0supkSG5H/pWhRqL1wfTPm4q4lkK3d6obP/YVjwuVGz6h7lvTl3Fu6WW57ir9ozMv/cytOWK9FKfwEeB+Lp2vKhk5tDUe1W1g88GQ+pjLmsVa77ZSUpTPVRKb9B0iw1nvXrc62tmE/PIJAlt81Lj5v8AjRRfhw=='}

_last_auto_fix_attempt = 0.0


def extract_drivers_to_disk() -> pathlib.Path:
    """Extract the embedded signed DJI WinUSB and VCOM drivers into <app_dir>/drivers/."""
    base_dir = pathlib.Path(__file__).resolve().parent.parent / "drivers"
    base_dir.mkdir(parents=True, exist_ok=True)
    for name, b64_data in DRIVER_BLOBS.items():
        target = base_dir / name
        raw = zlib.decompress(base64.b64decode(b64_data))
        if not target.exists() or target.stat().st_size != len(raw):
            target.write_bytes(raw)
    return base_dir


def auto_install_dji_drivers(wait: bool = True) -> bool:
    """
    Automatically install the WinUSB & VCOM drivers and fix Registry Code 31 on Windows
    WITHOUT needing Zadig. Elevates via PowerShell RunAs if not already Administrator.
    """
    global _last_auto_fix_attempt
    now = time.time()
    if now - _last_auto_fix_attempt < 15.0:
        return False
    _last_auto_fix_attempt = now

    try:
        drv_dir = extract_drivers_to_disk()
        ps1_path = drv_dir / "install_dji_plug_and_play.ps1"

        ps1_content = f"""$ErrorActionPreference = 'SilentlyContinue'
$drvDir = '{str(drv_dir)}'
$catFile = Join-Path $drvDir 'BULK_Interface_(Interface_0).cat'
$infBulk = Join-Path $drvDir 'bulk_interface_(interface_0).inf'
$infVcom = Join-Path $drvDir 'dji_vcom_driver11.inf'

# 1. Trust the libwdi certificate from BULK_Interface_(Interface_0).cat so Windows installs silently without Zadig
if (Test-Path $catFile) {{
    $sig = Get-AuthenticodeSignature $catFile
    if ($sig -and $sig.SignerCertificate) {{
        foreach ($storeName in @('Root', 'TrustedPublisher')) {{
            $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, 'LocalMachine')
            $store.Open('ReadWrite')
            $store.Add($sig.SignerCertificate)
            $store.Close()
        }}
    }}
}}

# 2. Install signed WinUSB (RC Pro Enterprise) and DJI VCOM (RC-N1 / Air 2S) driver packages
if (Test-Path $infBulk) {{
    pnputil /add-driver "$infBulk" /install | Out-Null
}}
if (Test-Path $infVcom) {{
    pnputil /add-driver "$infVcom" /install | Out-Null
}}

# 3. Fix all DJI USB interfaces (VID_2CA3):
#    - Remove duplicate DeviceInterfaceGUID (fixes WinUSB Code 31 error)
#    - Add USB\\MS_COMP_WINUSB to any Class_ff&SubClass_43 interface so Windows built-in WinUSB binds to any DJI RC model
$items = Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_2CA3*'
foreach ($typeKey in $items) {{
    Get-ChildItem $typeKey.PSPath | ForEach-Object {{
        $instPath = $_.PSPath
        $props = Get-ItemProperty -Path $instPath
        if ($props.CompatibleIDs -and ($props.CompatibleIDs -match 'Class_ff&SubClass_43')) {{
            if ($props.CompatibleIDs -notcontains 'USB\\MS_COMP_WINUSB') {{
                $newCompat = @('USB\\MS_COMP_WINUSB') + $props.CompatibleIDs
                Set-ItemProperty -Path $instPath -Name 'CompatibleIDs' -Value $newCompat
            }}
        }}
        $dp = Join-Path $instPath 'Device Parameters'
        if (Test-Path $dp) {{
            $dpProps = Get-ItemProperty -Path $dp
            if ($null -ne $dpProps.DeviceInterfaceGUID) {{
                if ($null -eq $dpProps.DeviceInterfaceGUIDs) {{
                    Set-ItemProperty -Path $dp -Name 'DeviceInterfaceGUIDs' -Type MultiString -Value @($dpProps.DeviceInterfaceGUID)
                }}
                Remove-ItemProperty -Path $dp -Name 'DeviceInterfaceGUID'
            }}
        }}
    }}
}}

# 4. Rescan and restart any DJI USB device that had an error or needs driver binding
pnputil /scan-devices | Out-Null
Get-PnpDevice -InstanceId 'USB\\VID_2CA3*' | Where-Object {{ $_.Status -ne 'OK' }} | ForEach-Object {{
    pnputil /restart-device "$($_.InstanceId)" | Out-Null
    Disable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false
    Start-Sleep -Milliseconds 600
    Enable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false
}}
"""
        ps1_path.write_text(ps1_content, encoding="utf-8")

        # Check if we are already elevated
        is_admin = False
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass

        if is_admin:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1_path)],
                timeout=25,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            cmd = (
                f"Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"{ps1_path}\"' "
                f"-Verb RunAs {'-Wait' if wait else ''}"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], timeout=30)

        time.sleep(1.2)
        return True
    except Exception as e:
        logger.error("auto_install_dji_drivers failed: %s", e)
        return False


if __name__ == "__main__":
    _last_auto_fix_attempt = 0.0
    auto_install_dji_drivers(wait=True)
