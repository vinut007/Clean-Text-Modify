' ============================================================================
' VModel VBA Text Cleaner
' Works in Excel: cleans CSV, Excel (this workbook), and ACCDB (Access) files.
' Fixes accents, symbols, mojibake hints, invisible chars, and collapses
' repeated punctuation (!!!??? -> !). 100% offline, no API needed.
' Mirrors the VModel Python pipeline (backend/core/clean.py, mappings.py).
' ============================================================================

Option Explicit

' ----------------------------------------------------------------------------
' Accent folding map — 401+ entries (Latin-1 Supplement, Latin Extended-A/B,
' Vietnamese precomposed, European precomposed). é -> e, ñ -> n, ü -> u, etc.
' ----------------------------------------------------------------------------
Private Function AccentMap() As Object
    Dim m As Object
    Set m = CreateObject("Scripting.Dictionary")
    m.CompareMode = 1 ' text-case-insensitive

    ' --- Latin-1 Supplement ---
    m("À") = "A": m("Á") = "A": m("Â") = "A": m("Ã") = "A": m("Ä") = "A": m("Å") = "A": m("Æ") = "AE"
    m("Ç") = "C": m("È") = "E": m("É") = "E": m("Ê") = "E": m("Ë") = "E": m("Ì") = "I": m("Í") = "I"
    m("Î") = "I": m("Ï") = "I": m("Ð") = "D": m("Ñ") = "N": m("Ò") = "O": m("Ó") = "O": m("Ô") = "O"
    m("Õ") = "O": m("Ö") = "O": m("Ø") = "O": m("Ù") = "U": m("Ú") = "U": m("Û") = "U": m("Ü") = "U"
    m("Ý") = "Y": m("Þ") = "Th": m("ß") = "ss"

    m("à") = "a": m("á") = "a": m("â") = "a": m("ã") = "a": m("ä") = "a": m("å") = "a": m("æ") = "ae"
    m("ç") = "c": m("è") = "e": m("é") = "e": m("ê") = "e": m("ë") = "e": m("ì") = "i": m("í") = "i"
    m("î") = "i": m("ï") = "i": m("ð") = "d": m("ñ") = "n": m("ò") = "o": m("ó") = "o": m("ô") = "o"
    m("õ") = "o": m("ö") = "o": m("ø") = "o": m("ù") = "u": m("ú") = "u": m("û") = "u": m("ü") = "u"
    m("ý") = "y": m("þ") = "th": m("ÿ") = "y"

    ' --- Latin Extended-A ---
    m("Ā") = "A": m("ā") = "a": m("Ă") = "A": m("ă") = "a": m("Ą") = "A": m("ą") = "a"
    m("Ć") = "C": m("ć") = "c": m("Ĉ") = "C": m("ĉ") = "c": m("Ċ") = "C": m("ċ") = "c": m("Č") = "C": m("č") = "c"
    m("Ď") = "D": m("ď") = "d": m("Đ") = "D": m("đ") = "d"
    m("Ē") = "E": m("ē") = "e": m("Ĕ") = "E": m("ĕ") = "e": m("Ė") = "E": m("ė") = "e": m("Ę") = "E": m("ę") = "e": m("Ě") = "E": m("ě") = "e"
    m("Ĝ") = "G": m("ĝ") = "g": m("Ğ") = "G": m("ğ") = "g": m("Ġ") = "G": m("ġ") = "g": m("Ģ") = "G": m("ģ") = "g"
    m("Ĥ") = "H": m("ĥ") = "h": m("Ħ") = "H": m("ħ") = "h"
    m("Ĩ") = "I": m("ĩ") = "i": m("Ī") = "I": m("ī") = "i": m("Ĭ") = "I": m("ĭ") = "i": m("Į") = "I": m("į") = "i": m("İ") = "I": m("ı") = "i"
    m("Ĵ") = "J": m("ĵ") = "j"
    m("Ķ") = "K": m("ķ") = "k": m("ĸ") = "k"
    m("Ĺ") = "L": m("ĺ") = "l": m("Ļ") = "L": m("ļ") = "l": m("Ľ") = "L": m("ľ") = "l": m("Ł") = "L": m("ł") = "l"
    m("Ń") = "N": m("ń") = "n": m("Ņ") = "N": m("ņ") = "n": m("Ň") = "N": m("ň") = "n": m("ŉ") = "n"
    m("Ō") = "O": m("ō") = "o": m("Ŏ") = "O": m("ŏ") = "o": m("Ő") = "O": m("ő") = "o": m("Œ") = "OE": m("œ") = "oe"
    m("Ŕ") = "R": m("ŕ") = "r": m("Ŗ") = "R": m("ŗ") = "r": m("Ř") = "R": m("ř") = "r"
    m("Ś") = "S": m("ś") = "s": m("Ŝ") = "S": m("ŝ") = "s": m("Ş") = "S": m("ş") = "s": m("Š") = "S": m("š") = "s"
    m("Ţ") = "T": m("ţ") = "t": m("Ť") = "T": m("ť") = "t": m("Ŧ") = "T": m("ŧ") = "t"
    m("Ũ") = "U": m("ũ") = "u": m("Ū") = "U": m("ū") = "u": m("Ŭ") = "U": m("ŭ") = "u": m("Ů") = "U": m("ů") = "u"
    m("Ű") = "U": m("ű") = "u": m("Ų") = "U": m("ų") = "u"
    m("Ŵ") = "W": m("ŵ") = "w"
    m("Ŷ") = "Y": m("ŷ") = "y": m("Ÿ") = "Y"
    m("Ź") = "Z": m("ź") = "z": m("Ż") = "Z": m("ż") = "z": m("Ž") = "Z": m("ž") = "z"

    ' --- Latin Extended-B ---
    m("ƀ") = "b": m("Ɓ") = "B": m("Ƃ") = "B": m("ƃ") = "b": m("Ƅ") = "b": m("ƅ") = "b": m("Ɔ") = "O": m("Ƈ") = "C"
    m("ƈ") = "c": m("Ɖ") = "D": m("Ɗ") = "D": m("Ƌ") = "d": m("ƌ") = "d": m("ƍ") = "d": m("Ǝ") = "E": m("Ə") = "E"
    m("Ɛ") = "E": m("Ƒ") = "F": m("ƒ") = "f": m("Ɠ") = "G": m("ɢ") = "g": m("Ɣ") = "G": m("Ɩ") = "I": m("Ɨ") = "I"
    m("Ƙ") = "K": m("ƙ") = "k": m("ƚ") = "l": m("ƛ") = "l": m("Ɯ") = "W": m("Ɲ") = "N": m("ƞ") = "n": m("Ɵ") = "O"
    m("Ơ") = "O": m("ơ") = "o": m("Ƣ") = "P": m("ƣ") = "p": m("Ƥ") = "P": m("ƥ") = "p": m("Ʀ") = "R": m("Ƨ") = "S"
    m("ƨ") = "s": m("Ʃ") = "S": m("ƪ") = "s": m("ƫ") = "t": m("Ƭ") = "T": m("ƭ") = "t": m("Ʈ") = "T": m("Ư") = "U"
    m("ư") = "u": m("Ʊ") = "U": m("Ʋ") = "V": m("Ƴ") = "Y": m("ƴ") = "y": m("Ƶ") = "Z": m("ƶ") = "z": m("Ʒ") = "Z"
    m("Ƹ") = "Z": m("ƹ") = "z": m("ƺ") = "z": m("ƻ") = "f": m("Ƽ") = "O": m("ƽ") = "o": m("ƾ") = "o": m("ƿ") = "w"
    m("ǀ") = "|": m("ǁ") = "|": m("ǂ") = "|": m("ǃ") = "!"
    m("Ǆ") = "D": m("ǅ") = "D": m("ǆ") = "d": m("Ǉ") = "L": m("ǈ") = "L": m("ǉ") = "l"
    m("Ǌ") = "N": m("ǋ") = "N": m("ǌ") = "n": m("Ǎ") = "A": m("ǎ") = "a": m("Ǐ") = "I": m("ǐ") = "i"
    m("Ǒ") = "O": m("ǒ") = "o": m("Ǔ") = "U": m("ǔ") = "u": m("Ǖ") = "U": m("ǖ") = "u": m("Ǘ") = "U": m("ǘ") = "u"
    m("Ǚ") = "U": m("ǚ") = "u": m("Ǜ") = "U": m("ǜ") = "u": m("ǝ") = "e": m("Ǟ") = "A": m("ǟ") = "a"
    m("Ǡ") = "A": m("ǡ") = "a": m("Ǣ") = "E": m("ǣ") = "e": m("Ǥ") = "G": m("ǥ") = "g": m("Ǧ") = "G": m("ǧ") = "g"
    m("Ǩ") = "K": m("ǩ") = "k": m("Ǫ") = "O": m("ǫ") = "o": m("Ǭ") = "O": m("ǭ") = "o": m("Ǯ") = "Z": m("ǯ") = "z"
    m("ǰ") = "j": m("Ǳ") = "D": m("ǲ") = "D": m("ǳ") = "d": m("Ǵ") = "G": m("ǵ") = "g": m("Ƕ") = "H": m("Ƿ") = "W"
    m("Ǹ") = "N": m("ǹ") = "n": m("Ǻ") = "A": m("ǻ") = "a": m("Ǽ") = "AE": m("ǽ") = "ae": m("Ǿ") = "O": m("ǿ") = "o"

    ' --- Vietnamese precomposed (tone marks) ---
    m("À") = "A": m("Á") = "A": m("Ả") = "A": m("Ã") = "A": m("Ạ") = "A"
    m("Â") = "A": m("Ầ") = "A": m("Ấ") = "A": m("Ẩ") = "A": m("Ẫ") = "A": m("Ậ") = "A"
    m("Ă") = "A": m("Ằ") = "A": m("Ắ") = "A": m("Ẳ") = "A": m("Ẵ") = "A": m("Ặ") = "A"
    m("È") = "E": m("É") = "E": m("Ẻ") = "E": m("Ẽ") = "E": m("Ẹ") = "E"
    m("Ê") = "E": m("Ề") = "E": m("Ế") = "E": m("Ể") = "E": m("Ễ") = "E": m("Ệ") = "E"
    m("Ì") = "I": m("Í") = "I": m("Ỉ") = "I": m("Ĩ") = "I": m("Ị") = "I"
    m("Ò") = "O": m("Ó") = "O": m("Ỏ") = "O": m("Õ") = "O": m("Ọ") = "O"
    m("Ô") = "O": m("Ồ") = "O": m("Ố") = "O": m("Ổ") = "O": m("Ỗ") = "O": m("Ộ") = "O"
    m("Ơ") = "O": m("Ờ") = "O": m("Ớ") = "O": m("Ở") = "O": m("Ỡ") = "O": m("Ợ") = "O"
    m("Ù") = "U": m("Ú") = "U": m("Ủ") = "U": m("Ũ") = "U": m("Ụ") = "U"
    m("Ư") = "U": m("Ừ") = "U": m("Ứ") = "U": m("Ử") = "U": m("Ữ") = "U": m("Ự") = "U"
    m("Ỳ") = "Y": m("Ý") = "Y": m("Ỷ") = "Y": m("Ỹ") = "Y": m("Ỵ") = "Y"
    m("Đ") = "D"

    m("à") = "a": m("á") = "a": m("ả") = "a": m("ã") = "a": m("ạ") = "a"
    m("â") = "a": m("ầ") = "a": m("ấ") = "a": m("ẩ") = "a": m("ẫ") = "a": m("ậ") = "a"
    m("ă") = "a": m("ằ") = "a": m("ắ") = "a": m("ẳ") = "a": m("ẵ") = "a": m("ặ") = "a"
    m("è") = "e": m("é") = "e": m("ẻ") = "e": m("ẽ") = "e": m("ẹ") = "e"
    m("ê") = "e": m("ề") = "e": m("ế") = "e": m("ể") = "e": m("ễ") = "e": m("ệ") = "e"
    m("ì") = "i": m("í") = "i": m("ỉ") = "i": m("ĩ") = "i": m("ị") = "i"
    m("ò") = "o": m("ó") = "o": m("ỏ") = "o": m("õ") = "o": m("ọ") = "o"
    m("ô") = "o": m("ồ") = "o": m("ố") = "o": m("ổ") = "o": m("ỗ") = "o": m("ộ") = "o"
    m("ơ") = "o": m("ờ") = "o": m("ớ") = "o": m("ở") = "o": m("ỡ") = "o": m("ợ") = "o"
    m("ù") = "u": m("ú") = "u": m("ủ") = "u": m("ũ") = "u": m("ụ") = "u"
    m("ư") = "u": m("ừ") = "u": m("ứ") = "u": m("ử") = "u": m("ữ") = "u": m("ự") = "u"
    m("ỳ") = "y": m("ý") = "y": m("ỷ") = "y": m("ỹ") = "y": m("ỵ") = "y"
    m("đ") = "d"

    ' --- Additional European precomposed ---
    m("Ǻ") = "A": m("ǻ") = "a": m("Ǽ") = "AE": m("ǽ") = "ae": m("Ǿ") = "O": m("ǿ") = "o"

    Set AccentMap = m
End Function

' ----------------------------------------------------------------------------
' Symbol map (curly quotes, dashes, etc.) — currency/trademark kept as-is
' ----------------------------------------------------------------------------
Private Function SymbolMap() As Object
    Dim m As Object
    Set m = CreateObject("Scripting.Dictionary")
    m.CompareMode = 1

    m("“") = """": m("”") = """": m("„") = """": m("‟") = """"
    m("‘") = "'": m("’") = "'": m("‚") = ",": m("‛") = "'"
    m("–") = "-": m("—") = "-": m("−") = "-": m("‐") = "-": m("‑") = "-"
    m("…") = "...": m("‥") = ".."
    m("·") = ".": m("•") = "*"
    m("×") = "x": m("÷") = "/"
    m("≤") = "<=": m("≥") = ">=": m("≠") = "!=": m("≈") = "~"
    m("±") = "+/-": m("°") = " deg"
    ' ™ ® © € £ ¥ ₹ ₽ ₩ ¢ ¤ kept as-is (not converted to letters)
    Set SymbolMap = m
End Function

' ----------------------------------------------------------------------------
' Pre-ftfy mojibake map (sequences Python ftfy mangles or needs help with)
' Applied before ftfy-equivalent repair. Sorted by length descending.
' ----------------------------------------------------------------------------
Private Function PreMojibakeMap() As Object
    Dim m As Object
    Set m = CreateObject("Scripting.Dictionary")
    m.CompareMode = 1

    m("â€•") = "•"        ' bullet
    m("â„¢") = "™"        ' trademark
    m("â€¬") = "a"        ' ftfy mangles to U+202C
    Set PreMojibakeMap = m
End Function

' ----------------------------------------------------------------------------
' Core text cleaner (mirrors the VModel Python pipeline)
' ----------------------------------------------------------------------------
Private Function CleanTextVBA(ByVal txt As String, _
                              Optional ByVal fixMojibake As Boolean = True, _
                              Optional ByVal foldAccents As Boolean = True, _
                              Optional ByVal foldSymbols As Boolean = True, _
                              Optional ByVal collapsePunct As Boolean = True, _
                              Optional ByVal keepEmoji As Boolean = True) As String

    Dim s As String
    s = txt
    If Len(s) = 0 Then CleanTextVBA = s: Exit Function

    ' --- 0. Pre-mojibake fixes: euro-with-digits then sequences needing help ---
    If fixMojibake Then
        Dim i As Long, n As Long, ch As String, c2 As String
        Dim out As String, j As Long
        n = Len(s)
        out = ""
        i = 1
        Do While i <= n
            ch = Mid(s, i, 1)
            ' â€ followed by digit -> euro € (protected as money)
            If ch = "â" And i + 1 <= n And Mid(s, i + 1, 1) = "€" And i + 2 <= n And Mid(s, i + 2, 1) Like "[0-9]" Then
                out = out & "€"
                i = i + 3
                Do While i <= n And Mid(s, i, 1) Like "[0-9]"
                    out = out & Mid(s, i, 1)
                    i = i + 1
                Loop
                i = i - 1
            ElseIf ch = "â" And i + 1 <= n And Mid(s, i + 1, 1) = "€" Then
                ' â€ standalone garbage -> a (negative lookahead: not followed by digit)
                out = out & "a"
                i = i + 2
            Else
                out = out & ch
            End If
            i = i + 1
        Loop
        s = out

        ' pre-mojibake map (ftfy-mangled sequences)
        Dim pm As Object, k As Variant, arrKeys
        Set pm = PreMojibakeMap
        arrKeys = pm.Keys
        QuickSortStrings arrKeys, LBound(arrKeys), UBound(arrKeys)
        For i = UBound(arrKeys) To LBound(arrKeys) Step -1
            k = arrKeys(i)
            If InStr(s, k) > 0 Then
                s = Replace(s, k, pm(k), 1, -1, 1)
            End If
        Next i
    End If

    ' --- 1. ftfy-equivalent repair: latin-1 -> utf-8 round trip ---
    If fixMojibake Then
        s = RepairMojibakeVBA(s)
    End If

    ' --- 2. Post-ftfy standalone mojibake fragments ---
    If fixMojibake Then
        Dim n2 As Long, i2 As Long, ch2 As String, c2b As String, out2 As String
        n2 = Len(s)
        out2 = ""
        i2 = 1
        Do While i2 <= n2
            ch2 = Mid(s, i2, 1)
            If ch2 = "â" And i2 + 1 <= n2 And Mid(s, i2 + 1, 1) = "€" Then
                ' standalone â€ -> a (not followed by digit, since digits handled pre-ftfy)
                out2 = out2 & "a"
                i2 = i2 + 2
            ElseIf ch2 = "Ã" And i2 + 1 <= n2 Then
                c2b = Mid(s, i2 + 1, 1)
                If AscW(c2b) < &H80 Or AscW(c2b) > &HFF Then
                    ' Ã not part of a mojibake sequence -> A
                    out2 = out2 & "A"
                    i2 = i2 + 1
                Else
                    out2 = out2 & ch2
                    i2 = i2 + 1
                End If
            ElseIf ch2 = "ã" And i2 + 1 <= n2 Then
                c2b = Mid(s, i2 + 1, 1)
                If AscW(c2b) < &H80 Or AscW(c2b) > &HFF Then
                    out2 = out2 & "a"
                    i2 = i2 + 1
                Else
                    out2 = out2 & ch2
                    i2 = i2 + 1
                End If
            Else
                out2 = out2 & ch2
                i2 = i2 + 1
            End If
        Loop
        s = out2
    End If

    ' --- 3. Accents ---
    If foldAccents Then
        Dim am As Object, ch3 As String * 1, j3 As Long, out3 As String
        Set am = AccentMap
        out3 = ""
        For j3 = 1 To Len(s)
            ch3 = Mid(s, j3, 1)
            If am.Exists(ch3) Then
                out3 = out3 & am(ch3)
            Else
                out3 = out3 & ch3
            End If
        Next j3
        s = out3
    End If

    ' --- 4. Symbols ---
    If foldSymbols Then
        Dim sm As Object
        Set sm = SymbolMap
        For Each k In sm.Keys
            If InStr(s, k) > 0 Then
                s = Replace(s, k, sm(k), 1, -1, 1)
            End If
        Next k
    End If

    ' --- 5. Invisible / control chars ---
    s = Replace(s, vbCrLf, " ")
    s = Replace(s, vbCr, " ")
    s = Replace(s, vbLf, " ")
    s = Replace(s, vbTab, " ")
    s = Replace(s, ChrW(&H00A0), " ")   ' NBSP -> space
    s = Replace(s, ChrW(&H3000), " ")   ' ideographic space -> space
    s = Replace(s, ChrW(&H200B), " ")   ' ZWSP -> space
    s = Replace(s, ChrW(&H200C), "")    ' ZWNJ -> remove (joiner)
    s = Replace(s, ChrW(&H200D), "")    ' ZWJ -> remove (joiner)
    s = Replace(s, ChrW(&HFEFF), "")    ' BOM -> remove
    s = Replace(s, ChrW(&H2060), "")    ' WJ -> remove
    s = Replace(s, ChrW(&H00AD), "")    ' soft hyphen -> remove
    ' collapse leftover exotic spaces -> space
    Dim sp As Variant
    For Each sp In Array(ChrW(&H2000), ChrW(&H2001), ChrW(&H2002), ChrW(&H2003), _
                         ChrW(&H2004), ChrW(&H2005), ChrW(&H2006), ChrW(&H2007), _
                         ChrW(&H2008), ChrW(&H2009), ChrW(&H200A), ChrW(&H202F), _
                         ChrW(&H205F), ChrW(&H3000))
        s = Replace(s, sp, " ")
    Next sp

    ' --- 6. Collapse repeated punctuation (!!!??? -> !) ---
    If collapsePunct Then
        s = CollapsePunctuationVBA(s)
    End If

    CleanTextVBA = s
End Function

' ----------------------------------------------------------------------------
' ftfy-equivalent: latin-1 -> utf-8 round trip for mojibake chunks
' ----------------------------------------------------------------------------
Private Function RepairMojibakeVBA(ByVal txt As String) As String
    Dim out As String, i As Long, n As Long, ch As String
    n = Len(txt)
    out = ""
    i = 1
    Do While i <= n
        ch = Mid(txt, i, 1)
        If AscW(ch) >= &H80 And AscW(ch) <= &HFF Then
            ' potential mojibake start — try latin-1 bytes -> utf-8 decode
            Dim buf As String, j As Long, b() As Byte, cj As String
            buf = ""
            j = i
            Do While j <= n
                cj = Mid(txt, j, 1)
                If AscW(cj) >= &H80 And AscW(cj) <= &HFF Then
                    buf = buf & cj
                    j = j + 1
                Else
                    Exit Do
                End If
            Loop
            If Len(buf) >= 1 Then
                b = StrConv(buf, vbFromUnicode) ' latin-1 bytes
                On Error Resume Next
                Dim decoded As String
                decoded = StrConv(b, vbUnicode) ' attempt utf-8 decode via VBA
                On Error GoTo 0
                If decoded <> "" And decoded <> buf Then
                    out = out & decoded
                    i = j
                Else
                    out = out & ch
                    i = i + 1
                End If
            Else
                out = out & ch
                i = i + 1
            End If
        Else
            out = out & ch
            i = i + 1
        End If
    Loop
    RepairMojibakeVBA = out
End Function

' ----------------------------------------------------------------------------
' Collapse runs of 3+ punctuation to first char (version guard: 1.0.0 kept)
' ----------------------------------------------------------------------------
Private Function CollapsePunctuationVBA(ByVal txt As String) As String
    Dim out As String, i As Long, n As Long, ch As String, j As Long
    Dim c2 As String, isVer As Boolean
    n = Len(txt)
    out = ""
    i = 1
    Do While i <= n
        ch = Mid(txt, i, 1)
        If IsPunctChar(ch) Then
            isVer = False
            If i > 1 And i < n Then
                c2 = Mid(txt, i - 1, 1)
                If c2 Like "[0-9]" Then
                    c2 = Mid(txt, i + 1, 1)
                    If c2 Like "[0-9]" And (ch = "." Or ch = "/" Or ch = "-") Then
                        isVer = True
                    End If
                End If
            End If
            If Not isVer Then
                j = i + 1
                Do While j <= n
                    c2 = Mid(txt, j, 1)
                    If IsPunctChar(c2) Or c2 Like "[0-9]" Then
                        j = j + 1
                    Else
                        Exit Do
                    End If
                Loop
                If j - i >= 3 Then
                    out = out & ch
                    i = j
                    Do While i <= n And (IsPunctChar(Mid(txt, i, 1)) Or Mid(txt, i, 1) Like "[0-9]")
                        i = i + 1
                    Loop
                    i = i - 1
                End If
            End If
        End If
        out = out & ch
        i = i + 1
    Loop
    CollapsePunctuationVBA = out
End Function

Private Function IsPunctChar(ByVal ch As String) As Boolean
    Dim p As String
    p = """!#$%&'()*+,-./:;<=>?@[\]^_`{|}~"
    IsPunctChar = (InStr(p, ch) > 0)
End Function

' ----------------------------------------------------------------------------
' QuickSort strings descending by length
' ----------------------------------------------------------------------------
Private Sub QuickSortStrings(ByRef arr, ByVal lo As Long, ByVal hi As Long)
    Dim pivot As String, i As Long, j As Long, tmp As String
    If lo < hi Then
        pivot = arr((lo + hi) \ 2)
        i = lo: j = hi
        Do While i <= j
            Do While Len(arr(i)) > Len(pivot): i = i + 1: Loop
            Do While Len(arr(j)) < Len(pivot): j = j - 1: Loop
            If i <= j Then
                tmp = arr(i): arr(i) = arr(j): arr(j) = tmp
                i = i + 1: j = j - 1
            End If
        Loop
        If lo < j Then QuickSortStrings arr, lo, j
        If i < hi Then QuickSortStrings arr, i, hi
    End If
End Sub

' ============================================================================
' UNIVERSAL FILE CLEANER — Excel (.xlsx/.xls) & CSV (.csv)
' Prompts for input file, auto-detects type, writes separate output file.
' ============================================================================

Public Sub CleanAnyFile()
    Dim fDialog As FileDialog
    Dim srcPath As String
    Dim ext As String
    
    Set fDialog = Application.FileDialog(msoFileDialogFilePicker)
    With fDialog
        .Title = "Select file to clean (Excel or CSV)"
        .Filters.Add "Excel & CSV", "*.xlsx; *.xls; *.csv"
        .Filters.Add "All Files", "*.*"
        .FilterIndex = 1
        .AllowMultiSelect = False
        If .Show <> -1 Then Exit Sub
        srcPath = .SelectedItems(1)
    End With
    
    ext = LCase(Mid(srcPath, InStrRev(srcPath, ".")))
    
    Select Case ext
        Case ".xlsx", ".xls"
            CleanExcelFile srcPath
        Case ".csv"
            CleanCsvFile srcPath
        Case Else
            MsgBox "Unsupported file type: " & ext, vbCritical, "VModel Cleaner"
    End Select
End Sub

' --- Clean an Excel file (xlsx/xls) — writes separate *_VModel_Cleaned.xlsx ---
Public Sub CleanExcelFile(ByVal srcPath As String)
    Dim xlApp As Object, xlWb As Object, ws As Object
    Dim cell As Object, outPath As String
    Dim totalCells As Long, changedCells As Long
    
    Set xlApp = CreateObject("Excel.Application")
    xlApp.Visible = False
    xlApp.DisplayAlerts = False
    
    Set xlWb = xlApp.Workbooks.Open(srcPath)
    outPath = srcPath & "_VModel_Cleaned.xlsx"
    
    totalCells = 0: changedCells = 0
    
    For Each ws In xlWb.Worksheets
        For Each cell In ws.UsedRange.Cells
            If VarType(cell.Value) = vbString And Len(cell.Value) > 0 Then
                totalCells = totalCells + 1
                If CleanTextVBA(cell.Value, True, True, True, True, True) <> cell.Value Then
                    changedCells = changedCells + 1
                    cell.Value = CleanTextVBA(cell.Value, True, True, True, True, True)
                End If
            End If
        Next cell
    Next ws
    
    xlWb.SaveAs outPath, 51  ' 51 = xlOpenXMLWorkbook (.xlsx)
    xlWb.Close SaveChanges:=False
    xlApp.Quit
    
    MsgBox "Excel cleaning complete." & vbCrLf & _
           "Cells scanned: " & totalCells & vbCrLf & _
           "Cells changed: " & changedCells & vbCrLf & _
           "Output: " & outPath, vbInformation, "VModel Cleaner"
End Sub

' --- Clean a CSV file — writes separate *_VModel_Cleaned.csv ---
Public Sub CleanCsvFile(ByVal srcPath As String, Optional ByVal outPath As String = "")
    Dim fnum As Integer, lineTxt As String, parts, i As Long
    Dim outNum As Integer, lineOut As String
    Dim totalCells As Long, changedCells As Long, cleaned As String
    
    If outPath = "" Then outPath = srcPath & "_VModel_Cleaned.csv"
    
    fnum = FreeFile
    Open srcPath For Input As #fnum
    outNum = FreeFile
    Open outPath For Output As #outNum
    
    totalCells = 0: changedCells = 0
    
    Do While Not EOF(fnum)
        Line Input #fnum, lineTxt
        parts = Split(lineTxt, ",")
        lineOut = ""
        For i = 0 To UBound(parts)
            cleaned = CleanTextVBA(parts(i), True, True, True, True, True)
            totalCells = totalCells + 1
            If cleaned <> parts(i) Then changedCells = changedCells + 1
            If i > 0 Then lineOut = lineOut & ","
            lineOut = lineOut & cleaned
        Next i
        Print #outNum, lineOut
    Loop
    Close #fnum
    Close #outNum
    
    MsgBox "CSV cleaning complete." & vbCrLf & _
           "Cells scanned: " & totalCells & vbCrLf & _
           "Cells changed: " & changedCells & vbCrLf & _
           "Output: " & outPath, vbInformation, "VModel Cleaner"
End Sub

' --- Clean the active worksheet ---------------------------------------------
Public Sub CleanActiveSheet()
    Dim cell As Range
    Application.ScreenUpdating = False
    For Each cell In ActiveSheet.UsedRange
        If VarType(cell.Value) = vbString And Len(cell.Value) > 0 Then
            cell.Value = CleanTextVBA(cell.Value, True, True, True, True, True)
        End If
    Next cell
    Application.ScreenUpdating = True
    MsgBox "Sheet cleaned.", vbInformation, "VModel Cleaner"
End Sub

' --- Clean all sheets in the active Excel workbook --------------------------
Public Sub CleanActiveWorkbook()
    Dim ws As Worksheet, cell As Range
    Application.ScreenUpdating = False
    For Each ws In ThisWorkbook.Worksheets
        For Each cell In ws.UsedRange
            If VarType(cell.Value) = vbString And Len(cell.Value) > 0 Then
                cell.Value = CleanTextVBA(cell.Value, True, True, True, True, True)
            End If
        Next cell
    Next ws
    Application.ScreenUpdating = True
    MsgBox "Workbook cleaned.", vbInformation, "VModel Cleaner"
End Sub

' --- Clean an ACCDB (Access) table via ADO ----------------------------------
Public Sub CleanAccdb(accdbPath As String, tableName As String, _
                      Optional ByVal idCol As String = "ID")
    Dim conn As Object, rs As Object, fld As Object
    On Error Resume Next
    Set conn = CreateObject("ADODB.Connection")
    conn.Provider = "Microsoft.ACE.OLEDB.12.0"
    conn.ConnectionString = "Data Source=" & accdbPath & ";"
    conn.Open
    If Err.Number <> 0 Then
        MsgBox "Cannot open ACCDB (need Access ACE driver): " & Err.Description, vbCritical
        Exit Sub
    End If
    On Error GoTo 0

    Set rs = CreateObject("ADODB.Recordset")
    rs.Open "SELECT * FROM [" & tableName & "]", conn, 1, 3

    Do While Not rs.EOF
        For Each fld In rs.Fields
            If (fld.Type = 202 Or fld.Type = 201) Then ' adVarWChar/adVarChar
                If Not IsNull(fld.Value) And Len(fld.Value) > 0 Then
                    fld.Value = CleanTextVBA(fld.Value, True, True, True, True, True)
                End If
            End If
        Next fld
        rs.Update
        rs.MoveNext
    Loop
    rs.Close
    conn.Close
    MsgBox "ACCDB cleaned: " & tableName, vbInformation, "VModel Cleaner"
End Sub

' ============================================================================
' EXAMPLE MACROS (run these from Alt+F8)
' ============================================================================

Public Sub DemoCleanActiveSheet()
    CleanActiveSheet
End Sub

Public Sub DemoCleanWorkbook()
    CleanActiveWorkbook
End Sub

Public Sub DemoCleanCsv()
    CleanCsvFile "C:\path\to\your\file.csv"
End Sub

Public Sub DemoCleanAccdb()
    CleanAccdb "C:\path\to\your\file.accdb", "YourTableName"
End Sub
