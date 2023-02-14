import pytest
import json
import os
from ens_normalize import *


TESTS_PATH = os.path.join(os.path.dirname(__file__), 'ens-normalize-tests.json')


@pytest.mark.parametrize(
    'fn,field',
    [
        (ens_normalize, 'norm'),
        (ens_beautify, 'beautified'),
    ]
)
def test_ens_normalize_full(fn, field):
    with open(TESTS_PATH) as f:
        data = json.load(f)

    good = 0
    bad = 0

    for test in data:
        name = test['name']

        if 'error' in test:
            try:
                fn(name)
                bad += 1
                print(f'! "{name}" did not throw "{test["comment"]}"')
            except ValueError:
                good += 1
        else:
            test['norm'] = test.get('norm', name)
            expected = test[field]

            try:
                actual = fn(name)
                if actual == expected:
                    good += 1
                else:
                    bad += 1
                    print(f'! "{name}" -> "{actual}" != "{expected}"')
            except ValueError as e:
                bad += 1
                print(f'! "{name}" threw "{e}"')

    assert bad == 0, f'{100 * good / (good + bad):.2f}%, {bad} failing'


def test_ens_beautify_xi():
    assert ens_beautify('ξabc') == 'Ξabc'
    assert ens_beautify('ξλφα') == 'ξλφα'
    assert ens_beautify('ξabc.ξλφα.ξabc.ξλφα') == 'Ξabc.ξλφα.Ξabc.ξλφα'


def test_ens_tokenize_full():
    with open(TESTS_PATH) as f:
        data = json.load(f)

    good = 0
    bad = 0

    for test in data:
        if 'tokenized' not in test:
            continue

        name = test['name']
        expected = test['tokenized']

        # we do not keep track of which tokens were changed
        for t in expected:
            if t['type'] == 'nfc':
                del t['tokens']
                del t['tokens0']

        res = [t._asdict() for t in ens_tokenize(name)]

        if res == expected:
            good += 1
        else:
            bad += 1
            print(f'! "{name}" tokenized incorrectly')

    assert bad == 0, f'{100 * good / (good + bad):.2f}%, {bad} failing'


@pytest.mark.parametrize('label,error,start,disallowed,suggested', [
    ('good', None, None, None, None),

    # underscore
    ('a_a', NormalizationErrorType.NORM_ERR_UNDERSCORE, 1, '_', ''),
    # --
    ('aa--a', NormalizationErrorType.NORM_ERR_HYPHEN, 2, '--', ''),
    # empty
    ("", NormalizationErrorType.NORM_ERR_EMPTY, 0, "", ""),

    # combining mark at the beginning
    ('\u0327a', NormalizationErrorType.NORM_ERR_CM_START, 0, '\u0327', ''),
    ('\u0327\u0327', NormalizationErrorType.NORM_ERR_CM_START, 0, '\u0327', ''),
    # combining mark after emoji
    ('a👩🏿‍🦲\u0327\u0327', NormalizationErrorType.NORM_ERR_CM_EMOJI, len('a👩🏿‍🦲'), '\u0327', ''),
    # more than one combining mark
    ('ك\u0622\u064D\u064Dك', NormalizationErrorType.NORM_ERR_CM_MULTI, 2, '\u064D', ''),

    # disallowed
    ('a?', NormalizationErrorType.NORM_ERR_DISALLOWED, 1, '?', ''),
    # disallowed/ignored invisible
    ('a\u200d', NormalizationErrorType.NORM_ERR_INVISIBLE, 1, '\u200d', ''),
    # ignored
    (f'a{chr(173)}', NormalizationErrorType.NORM_ERR_IGNORED, 1, chr(173), ''),  # invisible "soft hyphen"
    # mapped
    ('aA', NormalizationErrorType.NORM_ERR_MAPPED, 1, 'A', 'a'),
    # FE0F emoji
    ('a🚴‍♂️', NormalizationErrorType.NORM_ERR_FE0F, 1, '🚴‍♂️', '🚴‍♂'),
    # not NFC normalized
    ('aa\u0300b', NormalizationErrorType.NORM_ERR_NFC, 1, 'a\u0300', 'à'),

    # fenced
    # leading
    ("'ab", NormalizationErrorType.NORM_ERR_FENCED_LEADING, 0, "’", ""),
    # ("·ab", NormalizationErrorType.NORM_ERR_FENCED_LEADING, 0, "·", ""), # was disallowed
    ("⁄ab", NormalizationErrorType.NORM_ERR_FENCED_LEADING, 0, "⁄", ""),
    # multi
    ("a''b", NormalizationErrorType.NORM_ERR_FENCED_MULTI, 1, "’’", "’"),
    # ("a··b", NormalizationErrorType.NORM_ERR_FENCED_MULTI, 1, "··", "·"),
    ("a⁄⁄b", NormalizationErrorType.NORM_ERR_FENCED_MULTI, 1, "⁄⁄", "⁄"),
    ("a'⁄b", NormalizationErrorType.NORM_ERR_FENCED_MULTI, 1, "’⁄", "’"),
    # trailing
    ("ab'", NormalizationErrorType.NORM_ERR_FENCED_TRAILING, 2, "’", ""),
    # ("ab·", NormalizationErrorType.NORM_ERR_FENCED_TRAILING, 2, "·", ""),
    ("ab⁄", NormalizationErrorType.NORM_ERR_FENCED_TRAILING, 2, "⁄", ""),

    # confusables
    ('bitcoin.bitcοin.bi̇tcoin.bitсoin', NormalizationErrorType.NORM_ERR_CONF_MIXED, 12, 'ο', ''),
    ('0x.0χ.0х', NormalizationErrorType.NORM_ERR_CONF_WHOLE, None, None, None),
])
def test_ens_normalization_reason(label, error, start, disallowed, suggested):
    if error is None:
        assert ens_process(label, do_reason=True).error is None
    else:
        res = ens_process(label, do_reason=True)
        assert res.error.type == error
        assert res.error.start == start
        assert res.error.disallowed == disallowed
        assert res.error.suggested == suggested


@pytest.mark.parametrize(
    'error_type, code',
    [
        (NormalizationErrorType.NORM_ERR_UNDERSCORE, 'UNDERSCORE'),
        (NormalizationErrorType.NORM_ERR_HYPHEN, 'HYPHEN'),
        (NormalizationErrorType.NORM_ERR_CM_START, 'CM_START'),
        (NormalizationErrorType.NORM_ERR_CM_EMOJI, 'CM_EMOJI'),
        (NormalizationErrorType.NORM_ERR_CM_MULTI, 'CM_MULTI'),
        (NormalizationErrorType.NORM_ERR_DISALLOWED, 'DISALLOWED'),
        (NormalizationErrorType.NORM_ERR_INVISIBLE, 'INVISIBLE'),
        (NormalizationErrorType.NORM_ERR_IGNORED, 'IGNORED'),
        (NormalizationErrorType.NORM_ERR_MAPPED, 'MAPPED'),
        (NormalizationErrorType.NORM_ERR_FE0F, 'FE0F'),
        (NormalizationErrorType.NORM_ERR_NFC, 'NFC'),
    ]
)
def test_normalization_error_type_code(error_type: NormalizationErrorType, code: str):
    assert error_type.code == code


@pytest.mark.parametrize('text', [
    # multi char emoji
    'abc👩🏿‍🦲',
    # NFC
    'aa\u0300b',
    # mapped
    'a¼b'
    # ignored
    'a\xadb',
    # multi label
    'abc.abc.abc.abc',
    'abc.abc.abc👩🏿‍🦲.aa\u0300b.a¼b.a\xadb',
])
def test_ens_norm_error_pos(text):
    ret = ens_process(text + '_', do_reason=True)
    assert ret.error.type == NormalizationErrorType.NORM_ERR_UNDERSCORE
    assert ret.error.start == len(text)
    assert ret.error.disallowed == '_'
    assert ret.error.suggested == ''


def test_ens_norm_error_pos_disallowed():
    t = 'abc.abc.abc👩🏿‍🦲.aa\u0300b.a¼b.a\xadb'
    ret = ens_process(t + '?', do_reason=True)
    assert ret.error.type == NormalizationErrorType.NORM_ERR_DISALLOWED
    assert ret.error.start == len(t)
    assert ret.error.disallowed == '?'
    assert ret.error.suggested == ''


def test_ens_norm_error_pos_nfc():
    t = 'abc.abc.abc👩🏿‍🦲.ab.ab.ab'
    ret = ens_process(t + 'a\u0300', do_reason=True)
    assert ret.error.type == NormalizationErrorType.NORM_ERR_NFC
    assert ret.error.start == len(t)
    assert ret.error.disallowed == 'a\u0300'
    assert ret.error.suggested == 'à'
