from __future__ import annotations
from fast_antx.core import transfer


def run_antx_transfer_test() -> None:

    source_text = (
        "༄༅། །ཕྱག་ཆེན་སྔོན་འགྲོ་བཞི་སྦྱོར་དང་དངོས་གཞིའི་ཁྲིད་"
        "རིམ་མདོར་བསྡུས་ངེས་དོན་སྒྲོན་མེ་ཞེས་བྱ་བ་བཞུགས་སོ། །\n"
        "<𰵀auམཛད་པ་པོ། འཇམ་མགོན་ཀོང་སྤྲུལ་བློ་གྲོས་མཐའ་ཡས། །>\n"
        "༄༅། །ཕྱག་ཆེན་སྔོན་འགྲོ་བཞི་སྦྱོར་དང་དངོས་གཞིའི་ཁྲིད་"
        "རིམ་མདོར་བསྡུས་ངེས་དོན་སྒྲོན་མེ་ཞེས་བྱ་བ་བཞུགས་སོ། །\n"
    )
    target_text = (
        "༄༅། །ཕྱག་ཆེན་སྔོན་འགྲོ་བཞི་སྦྱོར་དང་དངོས་གཞིའི་ཁྲིད་"
        "རིམ་མདོར་བསྡུས་ངེས་དོན་སྒྲོན་མེ་ཞེས་བྱ་བ་བཞུགས་སོ། །\n"
        "མཛད་པ་པོ། འཇམ་མགོན་ཀོང་སྤྲུལ་བློ་གྲོས་མཐའ་ཡས། །\n"
        "༄༅། །ཕྱག་ཆེན་སྔོན་འགྲོ་བཞི་སྦྱོར་དང་དངོས་གཞིའི་ཁྲིད་"
        "རིམ་མདོར་བསྡུས་ངེས་དོན་སྒྲོན་མེ་ཞེས་བྱ་བ་བཞུགས་སོ། །\n"
        "༄༅། །གྲུབ་བརྒྱའི་སྤྱི་མེས་མར་མི་དྭགས་གསུམ་ནས། །དཔལ་"
        "ལྡན་དུས་གསུམ་མཁྱེན་པའི་བཀའ་བརྒྱུད་ནི།\n"
    )
    annotations = [
        ["author_start", r"(\<[𰵀-󴉱]?au)"],
        ["author_end", r"(\>)"],
    ]

    result = transfer(source_text, annotations, target_text, output="txt")
    print(result)

    expected_snippet = "<𰵀auམཛད་པ་པོ། འཇམ་མགོན་ཀོང་སྤྲུལ་བློ་གྲོས་མཐའ་ཡས། །>"
    assert expected_snippet in result, "Annotation transfer failed to insert tags."
    print("antx annotation transfer test passed.")


if __name__ == "__main__":
    run_antx_transfer_test()
