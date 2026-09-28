"""netcidr 的错误类型。

两个类的名字与含义是契约的一部分，不得改名、不得改含义（可以新增子类 / 新错误）。
"""


class ErrBadCidr(ValueError):
    """CIDR 文本非法：格式错误、前缀长度越界、地址不合法等。

    `netcidr.parse` 对任何无法解析成 `Range` 的输入都抛它。
    """


class ErrMixedFamily(ValueError):
    """同一次运算里混用了 IPv4 与 IPv6。

    `union` / `difference` 等要求参与的地址属于同一地址族；
    一个 `RangeSet` 里同时出现两种地址族即抛它。
    """
