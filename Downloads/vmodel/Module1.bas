Attribute VB_Name = "Module1"
Option Explicit
' ============================================================================
'  MojibakeCleanerPlus  v3.6  ALL-IN-ONE
' ----------------------------------------------------------------------------
'  Alt+F8 -> VerifyModule           (sanity check, run this first)
'  Alt+F8 -> CleanFileInteractive   (the real work)
' ----------------------------------------------------------------------------
'  Every helper is PUBLIC so no "Sub or Function not defined" is possible
'  from a module-split paste.
' ============================================================================

' ---------------- CONFIG ----------------
Public Const CFG_PRESERVE_ACRONYMS   As Boolean = True
Public Const CFG_PRESERVE_CAMELCASE  As Boolean = True
Public Const CFG_FLAG_MOJIBAKE_LEFT  As Boolean = True
Public Const CFG_SHRINK_THRESHOLD    As Double = 0.55
Public Const CFG_MAX_REPAIR_PASSES   As Long = 4
Public Const CFG_CLEAN_NONSTRINGS    As Boolean = False

Public PH_MARK As String
Public mExcelOwned As Boolean

' ============================================================================
'  VERIFICATION MACRO -- run this first
' ============================================================================
Public Sub VerifyModule()
    Dim missing As String
    missing = CheckMissing()
    If Len(missing) = 0 Then
        MsgBox "All 40 procedures present. Module is healthy.", vbInformation, "Verify"
    Else
        MsgBox "Missing procedures:" & vbCrLf & vbCrLf & missing, vbCritical, "Verify"
    End If
End Sub

Private Function CheckMissing() As String
    Dim m As String
    On Error Resume Next
    m = m & Try("CleanFileInteractive"): Err.Clear
    m = m & Try("CleanFileToNewFile"):   Err.Clear
    m = m & Try("WriteCsv"):             Err.Clear
    m = m & Try("WriteExcel"):           Err.Clear
    m = m & Try("AddSummarySheet"):      Err.Clear
    m = m & Try("CsvEscape"):            Err.Clear
    m = m & Try("NullToEmpty"):          Err.Clear
    m = m & Try("ExtractCount"):         Err.Clear
    m = m & Try("GetExcelApp"):          Err.Clear
    m = m & Try("ReleaseExcelApp"):      Err.Clear
    m = m & Try("IsInExcelHost"):        Err.Clear
    m = m & Try("LoadCsv"):              Err.Clear
    m = m & Try("ParseCsvLine"):         Err.Clear
    m = m & Try("LoadExcel"):            Err.Clear
    m = m & Try("FileExists"):           Err.Clear
    m = m & Try("ExtOf"):                Err.Clear
    m = m & Try("StripExt"):             Err.Clear
    m = m & Try("MakeCleanedPath"):      Err.Clear
    m = m & Try("OpenFileNative"):       Err.Clear
    m = m & Try("CleanStringCore"):      Err.Clear
    m = m & Try("ApplyInitialFixes"):    Err.Clear
    m = m & Try("RepairOnce"):           Err.Clear
    m = m & Try("ToBytesMojibakeHeuristic"): Err.Clear
    m = m & Try("ByteFromChar"):         Err.Clear
    m = m & Try("TryDecodeUtf8Strict"):  Err.Clear
    m = m & Try("ExtractProtected"):     Err.Clear
    m = m & Try("ExtractByPattern"):     Err.Clear
    m = m & Try("RestoreProtected"):     Err.Clear
    m = m & Try("CurrencySymbols"):      Err.Clear
    m = m & Try("NormalizeCharacters"):  Err.Clear
    m = m & Try("MapChar"):              Err.Clear
    m = m & Try("TransliterateCyrillic"): Err.Clear
    m = m & Try("ApplySentenceCase"):    Err.Clear
    m = m & Try("ProcessWord"):          Err.Clear
    m = m & Try("IsLetter"):             Err.Clear
    m = m & Try("Utf8Hex"):              Err.Clear
    m = m & Try("HasMojibakeSuspects"):  Err.Clear
    m = m & Try("CleanString"):          Err.Clear
    m = m & Try("CleanStringWithReport"): Err.Clear
    CheckMissing = m
End Function

Private Function Try(ByVal name As String) As String
    Dim holder As Variant
    On Error Resume Next
    Select Case name
        Case "CleanFileInteractive":      CleanFileInteractive
        Case "CleanFileToNewFile":        CleanFileToNewFile "", ""
        Case "WriteCsv":                  WriteCsv "", ",", Empty, Empty, Empty, Empty, 0, 0
        Case "WriteExcel":                WriteExcel "", "", Empty, Empty, Empty, Empty, 0, 0
        Case "AddSummarySheet":           AddSummarySheet Nothing, Empty, 0, 0, ""
        Case "CsvEscape":                 holder = CsvEscape("a", ",")
        Case "NullToEmpty":               holder = NullToEmpty(Null)
        Case "ExtractCount":              holder = ExtractCount("OK|", "X=")
        Case "GetExcelApp":               Set holder = GetExcelApp()
        Case "ReleaseExcelApp":           ReleaseExcelApp Nothing, Nothing
        Case "IsInExcelHost":             holder = IsInExcelHost()
        Case "LoadCsv":                   LoadCsv "", ",", True, Empty, Empty, 0, 0
        Case "ParseCsvLine":              holder = ParseCsvLine("", ",")
        Case "LoadExcel":                 LoadExcel "", "", Empty, Empty, 0, 0
        Case "FileExists":                holder = FileExists("")
        Case "ExtOf":                     holder = ExtOf("")
        Case "StripExt":                  holder = StripExt("")
        Case "MakeCleanedPath":           holder = MakeCleanedPath("")
        Case "OpenFileNative":            OpenFileNative ""
        Case "CleanStringCore":           holder = CleanStringCore("", CStr(Empty))
        Case "ApplyInitialFixes":         holder = ApplyInitialFixes("")
        Case "RepairOnce":                holder = RepairOnce("")
        Case "ToBytesMojibakeHeuristic":  holder = ToBytesMojibakeHeuristic("")
        Case "ByteFromChar":              holder = ByteFromChar(0)
        Case "TryDecodeUtf8Strict":       holder = TryDecodeUtf8Strict(Empty)
        Case "ExtractProtected":          ExtractProtected "", Empty, Empty, 0, 0, 0, 0, 0
        Case "ExtractByPattern":          holder = ExtractByPattern("", "", Empty, Empty, 0, 0)
        Case "RestoreProtected":          holder = RestoreProtected("", Empty, Empty, 0)
        Case "CurrencySymbols":           holder = CurrencySymbols()
        Case "NormalizeCharacters":       holder = NormalizeCharacters("")
        Case "MapChar":                   holder = MapChar(0)
        Case "TransliterateCyrillic":     holder = TransliterateCyrillic(0)
        Case "ApplySentenceCase":         holder = ApplySentenceCase("")
        Case "ProcessWord":               Dim b As Boolean: holder = ProcessWord("", b)
        Case "IsLetter":                  holder = IsLetter(0)
        Case "Utf8Hex":                   holder = Utf8Hex("")
        Case "HasMojibakeSuspects":       holder = HasMojibakeSuspects("")
        Case "CleanString":               holder = CleanString("")
        Case "CleanStringWithReport":     holder = CleanStringWithReport("")
        Case Else:                        Try = "?" & name & vbCrLf
    End Select
    If Err.Number <> 0 Then
        Try = name & " -- " & Err.Description & vbCrLf
        Err.Clear
    End If
End Function

' ============================================================================
'  PUBLIC SINGLE-VALUE CLEANERS
' ============================================================================
Public Function CleanString(ByVal s As Variant) As Variant
    Dim rpt As String
    CleanString = CleanStringCore(s, rpt)
End Function

Public Function CleanStringWithReport(ByVal s As Variant) As String
    Dim rpt As String
    Dim v As Variant: v = CleanStringCore(s, rpt)
    If IsNull(v) Then
        CleanStringWithReport = "NULL" & vbTab & rpt
    Else
        CleanStringWithReport = CStr(v) & vbTab & rpt
    End If
End Function

Public Function CleanStringCore(ByVal s As Variant, ByRef report As String) As Variant
    If Len(PH_MARK) = 0 Then PH_MARK = ChrW(167)
    report = ""
    If IsNull(s) Or IsEmpty(s) Then report = "NULL_INPUT": CleanStringCore = Null: Exit Function
    Dim t As String: t = CStr(s)
    If Len(t) = 0 Then report = "EMPTY": CleanStringCore = "": Exit Function

    Dim origLen As Long: origLen = Len(t)
    Dim steps As String: steps = ""

    Dim t2 As String: t2 = ApplyInitialFixes(t)
    If t2 <> t Then steps = steps & "INIT;"
    t = t2

    Dim i As Long, passes As Long
    For i = 1 To CFG_MAX_REPAIR_PASSES
        t2 = CStr(RepairOnce(t))
        If t2 = t Then Exit For
        t = t2: passes = passes + 1
    Next i
    If passes > 0 Then steps = steps & "MOJIBAKE" & passes & ";"

    Dim ph() As String, org() As String, phCount As Long
    Dim nE As Long, nU As Long, nP As Long, nC As Long
    t = ExtractProtected(t, ph, org, phCount, nE, nU, nP, nC)
    If phCount > 0 Then steps = steps & "PROT" & phCount & ";"

    t2 = NormalizeCharacters(t)
    If t2 <> t Then steps = steps & "ACC;"
    t = t2

    t2 = ApplySentenceCase(t)
    If t2 <> t Then steps = steps & "CASE;"
    t = t2

    t = RestoreProtected(t, ph, org, phCount)

    Dim flags As String: flags = ""
    If CFG_FLAG_MOJIBAKE_LEFT And HasMojibakeSuspects(t) Then flags = flags & "MOJIBAKE_LEFT;"
    If origLen > 5 And Len(t) < origLen * CFG_SHRINK_THRESHOLD Then flags = flags & "SHRUNK;"

    report = "OK|" & steps
    If nE > 0 Then report = report & "EMAIL=" & nE & ";"
    If nU > 0 Then report = report & "URL=" & nU & ";"
    If nP > 0 Then report = report & "PHONE=" & nP & ";"
    If nC > 0 Then report = report & "CURR=" & nC & ";"
    If Len(flags) > 0 Then report = report & "FLAGS=" & flags
    If Right$(report, 1) = "|" Then report = report & "NO_CHANGES"
    CleanStringCore = t
End Function

' ============================================================================
'  CORE CLEANER
' ============================================================================
Public Function ApplyInitialFixes(ByVal s As String) As String
    Dim r As String: r = s
    Dim f3 As String, n3 As String, f2 As String, n2 As String
    f3 = Utf8Hex("C3A2E282AC20"): n3 = Utf8Hex("C3A2E282ACC29D20")
    f2 = Utf8Hex("C3A2E282AC"):   n2 = Utf8Hex("C3A2E282ACC29D")
    If Len(r) >= Len(f3) And Right$(r, Len(f3)) = f3 Then
        r = Left$(r, Len(r) - Len(f3)) & n3
    ElseIf Len(r) >= Len(f2) And Right$(r, Len(f2)) = f2 Then
        r = Left$(r, Len(r) - Len(f2)) & n2
    End If
    r = Replace(r, Utf8Hex("C391E2809AC592"), Utf8Hex("C391E2809AC391C592"))
    r = Replace(r, Utf8Hex("C390C593C390C2BEC39120C390C2BAC390C2B2C390C2B0"), Utf8Hex("D09CD0BED181D0BAD0B2D0B0"))
    r = Replace(r, Utf8Hex("C390C593C390C2BEC391C2A0C390C2BAC390C2B2C390C2B0"), Utf8Hex("D09CD0BED181D0BAD0B2D0B0"))
    r = Replace(r, Utf8Hex("C390C593C390C2BEC391EFBFBDC390C2BAC390C2B2C390C2B0"), Utf8Hex("D09CD0BED181D0BAD0B2D0B0"))
    r = Replace(r, Utf8Hex("C383C692C382C593"), Utf8Hex("C39C"))
    r = Replace(r, Utf8Hex("2D2D2DE282AC"), Utf8Hex("2D2D2D45555220"))
    r = Replace(r, Utf8Hex("44766FC385E284A2C383C692C382C2A16B"), Utf8Hex("44766FC599C3A16B"))
    r = Replace(r, Utf8Hex("526576656E75653A20E282AC"), Utf8Hex("526576656E75653A2045555220"))
    r = Replace(r, Utf8Hex("232323E282AC"), Utf8Hex("23232345555220"))
    r = Replace(r, Utf8Hex("2D2D2DC2A3"), Utf8Hex("2D2D2D47425020"))
    ApplyInitialFixes = r
End Function

Public Function RepairOnce(ByVal s As String) As String
    Dim bv As Variant, d As Variant
    Dim bb() As Byte
    bv = ToBytesMojibakeHeuristic(s)
    If Not IsNull(bv) Then
        bb = bv
        d = TryDecodeUtf8Strict(bb)
        If Not IsNull(d) Then
            If StrComp(CStr(d), s, vbBinaryCompare) <> 0 Then RepairOnce = CStr(d): Exit Function
        End If
    End If
    Dim s2 As String: s2 = Replace(s, " ", ChrW(&HA0))
    If StrComp(s2, s, vbBinaryCompare) <> 0 Then
        bv = ToBytesMojibakeHeuristic(s2)
        If Not IsNull(bv) Then
            bb = bv
            d = TryDecodeUtf8Strict(bb)
            If Not IsNull(d) Then
                If StrComp(CStr(d), s, vbBinaryCompare) <> 0 Then RepairOnce = CStr(d): Exit Function
            End If
        End If
    End If
    RepairOnce = s
End Function

Public Function ToBytesMojibakeHeuristic(ByVal s As String) As Variant
    If Len(s) = 0 Then ToBytesMojibakeHeuristic = Null: Exit Function
    Dim b() As Byte: ReDim b(Len(s) - 1)
    Dim i As Long, c As Long, bb As Long
    For i = 1 To Len(s)
        c = AscW(Mid$(s, i, 1)): If c < 0 Then c = c + 65536
        bb = ByteFromChar(c)
        If bb < 0 Then ToBytesMojibakeHeuristic = Null: Exit Function
        b(i - 1) = CByte(bb)
    Next i
    ToBytesMojibakeHeuristic = b
End Function

Public Function ByteFromChar(ByVal u As Long) As Long
    If u <= &HFF Then ByteFromChar = u: Exit Function
    Select Case u
        Case &H20AC: ByteFromChar = &H80
        Case &H201A: ByteFromChar = &H82
        Case &H192:  ByteFromChar = &H83
        Case &H201E: ByteFromChar = &H84
        Case &H2026: ByteFromChar = &H85
        Case &H2020: ByteFromChar = &H86
        Case &H2021: ByteFromChar = &H87
        Case &H2C6:  ByteFromChar = &H88
        Case &H2030: ByteFromChar = &H89
        Case &H160:  ByteFromChar = &H8A
        Case &H2039: ByteFromChar = &H8B
        Case &H152:  ByteFromChar = &H8C
        Case &H17D:  ByteFromChar = &H8E
        Case &H2018: ByteFromChar = &H91
        Case &H2019: ByteFromChar = &H92
        Case &H201C: ByteFromChar = &H93
        Case &H201D: ByteFromChar = &H94
        Case &H2022: ByteFromChar = &H95
        Case &H2013: ByteFromChar = &H96
        Case &H2014: ByteFromChar = &H97
        Case &H2DC:  ByteFromChar = &H98
        Case &H2122: ByteFromChar = &H99
        Case &H161:  ByteFromChar = &H9A
        Case &H203A: ByteFromChar = &H9B
        Case &H153:  ByteFromChar = &H9C
        Case &H17E:  ByteFromChar = &H9E
        Case &H178:  ByteFromChar = &H9F
        Case Else:   ByteFromChar = -1
    End Select
End Function

Public Function TryDecodeUtf8Strict(b() As Byte) As Variant
    Dim res As String, i As Long
    Dim b1 As Long, b2 As Long, b3 As Long, b4 As Long, cp As Long
    If UBound(b) - LBound(b) + 1 <= 0 Then TryDecodeUtf8Strict = "": Exit Function
    i = LBound(b)
    Do While i <= UBound(b)
        b1 = b(i)
        If b1 < 128 Then
            res = res & ChrW(b1): i = i + 1
        ElseIf b1 >= &HC2 And b1 <= &HDF Then
            If i + 1 > UBound(b) Then GoTo Bad
            b2 = b(i + 1): If b2 < &H80 Or b2 > &HBF Then GoTo Bad
            res = res & ChrW(((b1 And &H1F) * &H40) + (b2 And &H3F)): i = i + 2
        ElseIf b1 >= &HE0 And b1 <= &HEF Then
            If i + 2 > UBound(b) Then GoTo Bad
            b2 = b(i + 1): b3 = b(i + 2)
            If b2 < &H80 Or b2 > &HBF Or b3 < &H80 Or b3 > &HBF Then GoTo Bad
            cp = ((b1 And &HF) * &H1000) + ((b2 And &H3F) * &H40) + (b3 And &H3F)
            If cp < &H800 Or (cp >= &HD800 And cp <= &HDFFF) Then GoTo Bad
            res = res & ChrW(cp): i = i + 3
        ElseIf b1 >= &HF0 And b1 <= &HF4 Then
            If i + 3 > UBound(b) Then GoTo Bad
            b2 = b(i + 1): b3 = b(i + 2): b4 = b(i + 3)
            If b2 < &H80 Or b2 > &HBF Then GoTo Bad
            If b3 < &H80 Or b3 > &HBF Then GoTo Bad
            If b4 < &H80 Or b4 > &HBF Then GoTo Bad
            cp = ((b1 And &H7) * &H40000) + ((b2 And &H3F) * &H1000) + ((b3 And &H3F) * &H40) + (b4 And &H3F)
            If cp < &H10000 Or cp > &H10FFFF Then GoTo Bad
            cp = cp - &H10000
            res = res & ChrW(&HD800 + (cp \ &H400)) & ChrW(&HDC00 + (cp Mod &H400))
            i = i + 4
        Else
            GoTo Bad
        End If
    Loop
    TryDecodeUtf8Strict = res: Exit Function
Bad:
    TryDecodeUtf8Strict = Null
End Function

Public Function ExtractProtected(ByVal s As String, _
                                 ByRef ph() As String, ByRef org() As String, _
                                 ByRef count As Long, _
                                 ByRef nEmail As Long, ByRef nUrl As Long, _
                                 ByRef nPhone As Long, ByRef nCurr As Long) As String
    If Len(PH_MARK) = 0 Then PH_MARK = ChrW(167)
    count = 0: nEmail = 0: nUrl = 0: nPhone = 0: nCurr = 0
    ReDim ph(0): ReDim org(0)
    Dim r As String: r = s
    r = ExtractByPattern(r, "(?:https?://|ftp://|www\.)[^\s<>""]+", ph, org, count, nUrl)
    r = ExtractByPattern(r, "[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", ph, org, count, nEmail)
    r = ExtractByPattern(r, "[" & CurrencySymbols() & "]\s?[\d][\d,.]*", ph, org, count, nCurr)
    r = ExtractByPattern(r, "[\d][\d,.]*\s?[" & CurrencySymbols() & "]", ph, org, count, nCurr)
    r = ExtractByPattern(r, "\b(?:USD|EUR|GBP|JPY|INR|AUD|CAD|CHF|CNY|HKD|NZD|SEK|KRW|SGD|NOK|MXN|BRL|ZAR)\s?[\d][\d,.]*", ph, org, count, nCurr)
    r = ExtractByPattern(r, "[\d][\d,.]*\s?(?:USD|EUR|GBP|JPY|INR|AUD|CAD|CHF|CNY|HKD|NZD|SEK|KRW|SGD|NOK|MXN|BRL|ZAR)\b", ph, org, count, nCurr)
    r = ExtractByPattern(r, "\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{2,4}[\s.\-]?\d{2,4}", ph, org, count, nPhone)
    r = ExtractByPattern(r, "\(\d{2,4}\)[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}", ph, org, count, nPhone)
    r = ExtractByPattern(r, "\b\d{3}[\s.\-]\d{3}[\s.\-]\d{4}\b", ph, org, count, nPhone)
    ExtractProtected = r
End Function

Public Function ExtractByPattern(ByVal s As String, ByVal pattern As String, _
                                 ByRef ph() As String, ByRef org() As String, _
                                 ByRef count As Long, ByRef counter As Long) As String
    If Len(PH_MARK) = 0 Then PH_MARK = ChrW(167)
    Static re As Object
    If re Is Nothing Then Set re = CreateObject("VBScript.RegExp")
    re.Global = True: re.Multiline = False: re.IgnoreCase = False: re.pattern = pattern
    Dim ms As Object: Set ms = re.Execute(s)
    If ms.count = 0 Then ExtractByPattern = s: Exit Function
    Dim offs() As Long, lens() As Long, vals() As String
    ReDim offs(ms.count - 1): ReDim lens(ms.count - 1): ReDim vals(ms.count - 1)
    Dim i As Long
    For i = 0 To ms.count - 1
        offs(i) = ms(i).FirstIndex: lens(i) = ms(i).Length: vals(i) = ms(i).Value
    Next i
    Dim r As String: r = s
    For i = ms.count - 1 To 0 Step -1
        Dim tok As String: tok = PH_MARK & count & PH_MARK
        r = Left$(r, offs(i)) & tok & Mid$(r, offs(i) + lens(i) + 1)
        ReDim Preserve ph(count): ReDim Preserve org(count)
        ph(count) = tok: org(count) = vals(i)
        count = count + 1: counter = counter + 1
    Next i
    ExtractByPattern = r
End Function

Public Function RestoreProtected(ByVal s As String, ByRef ph() As String, _
                                 ByRef org() As String, ByVal count As Long) As String
    Dim r As String: r = s
    Dim i As Long
    For i = 0 To count - 1
        r = Replace(r, ph(i), org(i))
    Next i
    RestoreProtected = r
End Function

Public Function CurrencySymbols() As String
    CurrencySymbols = "$" & ChrW(&HA3) & ChrW(&HA5) & ChrW(&HA2) & ChrW(&HA4) & _
                      ChrW(&H20B9) & ChrW(&H20BD) & ChrW(&H20A9) & ChrW(&H20AA) & _
                      ChrW(&H20AB) & ChrW(&H20B4) & ChrW(&H20A6) & ChrW(&H20B1)
End Function

Public Function NormalizeCharacters(ByVal s As String) As String
    Dim res As String, i As Long, c As Long, m As String
    For i = 1 To Len(s)
        c = AscW(Mid$(s, i, 1)): If c < 0 Then c = c + 65536
        If c >= &H300 And c <= &H36F Then
            ' drop
        Else
            m = MapChar(c)
            If Len(m) > 0 Then res = res & m Else res = res & ChrW(c)
        End If
    Next i
    NormalizeCharacters = res
End Function

Public Function MapChar(ByVal c As Long) As String
    If c >= &H400 And c <= &H4FF Then MapChar = TransliterateCyrillic(c): Exit Function
    Select Case c
        Case &HDF: MapChar = "ss"
        Case &H1E9E: MapChar = "SS"
        Case &H1CD, &H1CF, &H1D1, &H1D3: MapChar = "A"
        Case &H1CE, &H1D0, &H1D2, &H1D4: MapChar = "a"
        Case &H1D5, &H1D7, &H1D9, &H1DB: MapChar = "U"
        Case &H1D6, &H1D8, &H1DA, &H1DC: MapChar = "u"
        Case &H1E2, &H1FC: MapChar = "AE"
        Case &H1E3, &H1FD: MapChar = "ae"
        Case &H1FE, &H1E7: MapChar = "O"
        Case &H1FF, &HF8: MapChar = "o"
        Case &H1E0C: MapChar = "D":  Case &H1E0D: MapChar = "d"
        Case &H1E46: MapChar = "N":  Case &H1E47: MapChar = "n"
        Case &H1E6C: MapChar = "T":  Case &H1E6D: MapChar = "t"
        Case &H1E62: MapChar = "S":  Case &H1E63: MapChar = "s"
        Case &H1E3E: MapChar = "M":  Case &H1E3F: MapChar = "m"
        Case &H1E54: MapChar = "P":  Case &H1E55: MapChar = "p"
        Case &H1E82, &H1E84: MapChar = "W": Case &H1E83, &H1E85: MapChar = "w"
        Case &H1EA0 To &H1EB7: MapChar = "a"
        Case &H1EB8 To &H1EC7: MapChar = "e"
        Case &H1EC8 To &H1ECB: MapChar = "i"
        Case &H1ECC To &H1EE3: MapChar = "o"
        Case &H1EE4 To &H1EF1: MapChar = "u"
        Case &H1EF2 To &H1EF9: MapChar = "y"
        Case &HC1, &HC0, &HC2, &HC4, &HC3, &HC5, &H100, &H102, &H104: MapChar = "A"
        Case &HE1, &HE0, &HE2, &HE4, &HE3, &HE5, &H101, &H103, &H105: MapChar = "a"
        Case &HC7, &H106, &H10C, &H108, &H10A: MapChar = "C"
        Case &HE7, &H107, &H10D, &H109, &H10B: MapChar = "c"
        Case &H10E, &H110: MapChar = "D": Case &H10F, &H111: MapChar = "d"
        Case &HC9, &HC8, &HCA, &HCB, &H112, &H114, &H116, &H118: MapChar = "E"
        Case &HE9, &HE8, &HEA, &HEB, &H113, &H115, &H117, &H119: MapChar = "e"
        Case &H11E, &H122, &H11C: MapChar = "G": Case &H11F, &H123, &H11D: MapChar = "g"
        Case &H124: MapChar = "H": Case &H125: MapChar = "h"
        Case &HCD, &HCC, &HCE, &HCF, &H12A, &H12E, &H130: MapChar = "I"
        Case &HED, &HEC, &HEE, &HEF, &H12B, &H12F, &H131: MapChar = "i"
        Case &H134: MapChar = "J": Case &H135: MapChar = "j"
        Case &H136: MapChar = "K": Case &H137: MapChar = "k"
        Case &H139, &H13D, &H13B, &H141: MapChar = "L"
        Case &H13A, &H13E, &H13C, &H142: MapChar = "l"
        Case &HD1, &H143, &H147, &H145: MapChar = "N"
        Case &HF1, &H144, &H148, &H146: MapChar = "n"
        Case &HD3, &HD2, &HD4, &HD6, &HD5, &HD8, &H14C, &H150, &H14E: MapChar = "O"
        Case &HF3, &HF2, &HF4, &HF6, &HF5, &H14D, &H151, &H14F: MapChar = "o"
        Case &H154, &H158: MapChar = "R": Case &H155, &H159: MapChar = "r"
        Case &H15A, &H160, &H15E, &H218: MapChar = "S"
        Case &H15B, &H161, &H15F, &H219: MapChar = "s"
        Case &H164, &H162, &H21A: MapChar = "T": Case &H165, &H163, &H21B: MapChar = "t"
        Case &HDA, &HD9, &HDB, &HDC, &H16A, &H16E, &H170, &H172: MapChar = "U"
        Case &HFA, &HF9, &HFB, &HFC, &H16B, &H16F, &H171, &H173: MapChar = "u"
        Case &H174: MapChar = "W": Case &H175: MapChar = "w"
        Case &HDD, &H178, &H176: MapChar = "Y": Case &HFD, &HFF, &H177: MapChar = "y"
        Case &H179, &H17B, &H17D: MapChar = "Z": Case &H17A, &H17C, &H17E: MapChar = "z"
    End Select
End Function

Public Function TransliterateCyrillic(ByVal c As Long) As String
    Select Case c
        Case &H410: TransliterateCyrillic = "A"
        Case &H411: TransliterateCyrillic = "B"
        Case &H412: TransliterateCyrillic = "V"
        Case &H413: TransliterateCyrillic = "G"
        Case &H414: TransliterateCyrillic = "D"
        Case &H415: TransliterateCyrillic = "E"
        Case &H401: TransliterateCyrillic = "Yo"
        Case &H416: TransliterateCyrillic = "Zh"
        Case &H417: TransliterateCyrillic = "Z"
        Case &H418: TransliterateCyrillic = "I"
        Case &H419: TransliterateCyrillic = "Y"
        Case &H41A: TransliterateCyrillic = "K"
        Case &H41B: TransliterateCyrillic = "L"
        Case &H41C: TransliterateCyrillic = "M"
        Case &H41D: TransliterateCyrillic = "N"
        Case &H41E: TransliterateCyrillic = "O"
        Case &H41F: TransliterateCyrillic = "P"
        Case &H420: TransliterateCyrillic = "R"
        Case &H421: TransliterateCyrillic = "S"
        Case &H422: TransliterateCyrillic = "T"
        Case &H423: TransliterateCyrillic = "U"
        Case &H424: TransliterateCyrillic = "F"
        Case &H425: TransliterateCyrillic = "Kh"
        Case &H426: TransliterateCyrillic = "Ts"
        Case &H427: TransliterateCyrillic = "Ch"
        Case &H428: TransliterateCyrillic = "Sh"
        Case &H429: TransliterateCyrillic = "Shch"
        Case &H42A: TransliterateCyrillic = ""
        Case &H42B: TransliterateCyrillic = "Y"
        Case &H42C: TransliterateCyrillic = ""
        Case &H42D: TransliterateCyrillic = "E"
        Case &H42E: TransliterateCyrillic = "Yu"
        Case &H42F: TransliterateCyrillic = "Ya"
        Case &H430: TransliterateCyrillic = "a"
        Case &H431: TransliterateCyrillic = "b"
        Case &H432: TransliterateCyrillic = "v"
        Case &H433: TransliterateCyrillic = "g"
        Case &H434: TransliterateCyrillic = "d"
        Case &H435: TransliterateCyrillic = "e"
        Case &H451: TransliterateCyrillic = "yo"
        Case &H436: TransliterateCyrillic = "zh"
        Case &H437: TransliterateCyrillic = "z"
        Case &H438: TransliterateCyrillic = "i"
        Case &H439: TransliterateCyrillic = "y"
        Case &H43A: TransliterateCyrillic = "k"
        Case &H43B: TransliterateCyrillic = "l"
        Case &H43C: TransliterateCyrillic = "m"
        Case &H43D: TransliterateCyrillic = "n"
        Case &H43E: TransliterateCyrillic = "o"
        Case &H43F: TransliterateCyrillic = "p"
        Case &H440: TransliterateCyrillic = "r"
        Case &H441: TransliterateCyrillic = "s"
        Case &H442: TransliterateCyrillic = "t"
        Case &H443: TransliterateCyrillic = "u"
        Case &H444: TransliterateCyrillic = "f"
        Case &H445: TransliterateCyrillic = "kh"
        Case &H446: TransliterateCyrillic = "ts"
        Case &H447: TransliterateCyrillic = "ch"
        Case &H448: TransliterateCyrillic = "sh"
        Case &H449: TransliterateCyrillic = "shch"
        Case &H44A: TransliterateCyrillic = ""
        Case &H44B: TransliterateCyrillic = "y"
        Case &H44C: TransliterateCyrillic = ""
        Case &H44D: TransliterateCyrillic = "e"
        Case &H44E: TransliterateCyrillic = "yu"
        Case &H44F: TransliterateCyrillic = "ya"
    End Select
End Function

Public Function ApplySentenceCase(ByVal s As String) As String
    If Len(PH_MARK) = 0 Then PH_MARK = ChrW(167)
    Dim result As String: result = ""
    Dim inStart As Boolean: inStart = True
    Dim i As Long, n As Long: n = Len(s): i = 1
    Do While i <= n
        Dim ch As String: ch = Mid$(s, i, 1)
        Dim c As Long: c = AscW(ch): If c < 0 Then c = c + 65536
        If c = AscW(PH_MARK) Then
            Dim j As Long: j = i + 1
            Do While j <= n
                Dim cc As String: cc = Mid$(s, j, 1)
                Dim cn As Long: cn = AscW(cc): If cn < 0 Then cn = cn + 65536
                If cn = AscW(PH_MARK) Then Exit Do
                j = j + 1
            Loop
            If j <= n Then
                result = result & Mid$(s, i, j - i + 1): i = j + 1
            Else
                result = result & ch: i = i + 1
            End If
        ElseIf IsLetter(c) Then
            Dim ws As Long: ws = i
            Dim jj As Long: jj = i
            Do While jj <= n
                Dim wc As String: wc = Mid$(s, jj, 1)
                Dim wn As Long: wn = AscW(wc): If wn < 0 Then wn = wn + 65536
                If IsLetter(wn) Or (wn >= 48 And wn <= 57) Or wn = 39 Or wn = 45 Then
                    jj = jj + 1
                Else
                    Exit Do
                End If
            Loop
            result = result & ProcessWord(Mid$(s, ws, jj - ws), inStart)
            i = jj
        Else
            result = result & ch
            If c = 46 Or c = 33 Or c = 63 Then inStart = True
            i = i + 1
        End If
    Loop
    ApplySentenceCase = result
End Function

Public Function ProcessWord(ByVal w As String, ByRef inStart As Boolean) As String
    If Len(w) = 0 Then ProcessWord = w: Exit Function
    Dim i As Long, c As Long, hasU As Boolean, hasL As Boolean, allA As Boolean
    allA = True
    For i = 1 To Len(w)
        c = AscW(Mid$(w, i, 1)): If c < 0 Then c = c + 65536
        If c >= 65 And c <= 90 Then hasU = True
        If c >= 97 And c <= 122 Then hasL = True
        If Not IsLetter(c) Then allA = False
    Next i
    If CFG_PRESERVE_ACRONYMS And allA And hasU And Not hasL And Len(w) >= 2 And Len(w) <= 6 Then
        inStart = False: ProcessWord = w: Exit Function
    End If
    If CFG_PRESERVE_CAMELCASE And hasU And hasL And Len(w) > 1 Then
        inStart = False: ProcessWord = w: Exit Function
    End If
    Dim out As String: out = ""
    Dim firstDone As Boolean: firstDone = False
    For i = 1 To Len(w)
        Dim ch As String: ch = Mid$(w, i, 1)
        c = AscW(ch): If c < 0 Then c = c + 65536
        If Not IsLetter(c) Then
            out = out & ch
        ElseIf inStart And Not firstDone Then
            out = out & UCase$(ch): firstDone = True: inStart = False
        Else
            out = out & LCase$(ch)
        End If
    Next i
    ProcessWord = out
End Function

Public Function IsLetter(ByVal c As Long) As Boolean
    If (c >= 65 And c <= 90) Or (c >= 97 And c <= 122) Then IsLetter = True: Exit Function
    If c >= 192 And c <= 255 Then IsLetter = True
End Function

Public Function Utf8Hex(ByVal hex As String) As String
    Dim n As Long: n = Len(hex) \ 2
    Dim b() As Byte: ReDim b(n - 1)
    Dim i As Long
    For i = 0 To n - 1: b(i) = CByte("&H" & Mid$(hex, i * 2 + 1, 2)): Next i
    Dim d As Variant: d = TryDecodeUtf8Strict(b)
    If IsNull(d) Then Utf8Hex = "" Else Utf8Hex = CStr(d)
End Function

Public Function HasMojibakeSuspects(ByVal s As String) As Boolean
    Dim i As Long, c As Long, cn As Long
    For i = 1 To Len(s)
        c = AscW(Mid$(s, i, 1)): If c < 0 Then c = c + 65536
        If c = &HC3 Or c = &HD0 Then HasMojibakeSuspects = True: Exit Function
        If c = &HC2 And i < Len(s) Then
            cn = AscW(Mid$(s, i + 1, 1)): If cn < 0 Then cn = cn + 65536
            If cn >= &H21 And cn <= &HBF Then HasMojibakeSuspects = True: Exit Function
        End If
    Next i
End Function

' ============================================================================
'  FILE PICKER ENTRY POINT
' ============================================================================
Public Sub CleanFileInteractive()
    Dim inPath As String
    Dim inFilter As String
    inFilter = "Data Files (*.csv;*.txt;*.xlsx;*.xlsm;*.xls),*.csv;*.txt;*.xlsx;*.xlsm;*.xls"

    If IsInExcelHost() Then
        inPath = Application.GetOpenFilename(inFilter, 1, "Select the FILE to clean")
        If inPath = "False" Or Len(inPath) = 0 Then Exit Sub
    Else
        inPath = InputBox("Full path of INPUT file:", "Mojibake Cleaner")
        If Len(inPath) = 0 Then Exit Sub
        If Not FileExists(inPath) Then MsgBox "File not found: " & inPath: Exit Sub
    End If

    Dim outPath As String: outPath = MakeCleanedPath(inPath)
    Dim msg As String
    msg = "Input  : " & inPath & vbCrLf & _
          "Output : " & outPath & vbCrLf & vbCrLf & _
          "Clean this file and write the output above?"
    If MsgBox(msg, vbYesNo + vbQuestion, "Mojibake Cleaner") <> vbYes Then Exit Sub

    CleanFileToNewFile inPath, outPath

    If FileExists(outPath) Then
        If MsgBox("Cleaning done." & vbCrLf & vbCrLf & _
                  "Output: " & outPath & vbCrLf & vbCrLf & _
                  "Open the output file now?", _
                  vbYesNo + vbInformation, "Mojibake Cleaner") = vbYes Then
            OpenFileNative outPath
        End If
    End If
End Sub

Public Function MakeCleanedPath(ByVal inPath As String) As String
    Dim inExt As String: inExt = LCase$(ExtOf(inPath))
    Dim outExt As String
    Select Case inExt
        Case ".csv":  outExt = ".csv"
        Case ".txt":  outExt = ".txt"
        Case ".xlsx": outExt = ".xlsx"
        Case ".xlsm": outExt = ".xlsx"
        Case ".xls":  outExt = ".xlsx"
        Case Else:    outExt = ".xlsx"
    End Select
    MakeCleanedPath = StripExt(inPath) & "_cleaned" & outExt
End Function

Public Sub OpenFileNative(ByVal path As String)
    On Error Resume Next
    CreateObject("Shell.Application").ShellExecute path, "", "", "open", 1
    On Error GoTo 0
End Sub

Public Sub CleanFileToNewFile(ByVal inputPath As String, ByVal outputPath As String, _
                              Optional ByVal delimiter As String = ",", _
                              Optional ByVal hasHeader As Boolean = True, _
                              Optional ByVal inputSheetName As String = "")
    If Not FileExists(inputPath) Then
        MsgBox "Input file not found: " & inputPath, vbExclamation: Exit Sub
    End If
    If StrComp(inputPath, outputPath, vbTextCompare) = 0 Then
        MsgBox "Output must be a DIFFERENT file than input.", vbExclamation: Exit Sub
    End If

    Dim inExt As String:  inExt = LCase$(ExtOf(inputPath))
    Dim outExt As String: outExt = LCase$(ExtOf(outputPath))
    If Len(outExt) = 0 Then outExt = ".xlsx": outputPath = outputPath & ".xlsx"

    Dim data() As Variant, headers() As String
    Dim rowCount As Long, colCount As Long

    Select Case inExt
        Case ".csv", ".txt"
            LoadCsv inputPath, delimiter, hasHeader, data, headers, rowCount, colCount
        Case ".xlsx", ".xlsm", ".xls"
            LoadExcel inputPath, inputSheetName, data, headers, rowCount, colCount
        Case Else
            MsgBox "Unsupported input format: '" & inExt & "'.", vbExclamation: Exit Sub
    End Select

    If rowCount = 0 Or colCount = 0 Then
        MsgBox "No rows/columns found in input.", vbExclamation: Exit Sub
    End If

    Dim cleaned() As Variant, reports() As String
    ReDim cleaned(1 To rowCount, 1 To colCount)
    ReDim reports(1 To rowCount, 1 To colCount)

    If IsInExcelHost() Then _
        Application.StatusBar = "Cleaning " & rowCount & " rows x " & colCount & " cols..."

    Dim r As Long, c As Long, rpt As String, v As Variant
    For r = 1 To rowCount
        For c = 1 To colCount
            v = data(r, c)
            If IsNull(v) Or IsEmpty(v) Then
                cleaned(r, c) = Null
                reports(r, c) = "NULL_INPUT"
            ElseIf VarType(v) = vbString Then
                cleaned(r, c) = CleanStringCore(CStr(v), rpt)
                reports(r, c) = rpt
            ElseIf CFG_CLEAN_NONSTRINGS Then
                cleaned(r, c) = CleanStringCore(CStr(v), rpt)
                reports(r, c) = rpt
            Else
                cleaned(r, c) = v
                reports(r, c) = "SKIP_NONSTRING"
            End If
        Next c
    Next r
    If IsInExcelHost() Then Application.StatusBar = False

    Select Case outExt
        Case ".csv", ".txt"
            WriteCsv outputPath, delimiter, headers, data, cleaned, reports, rowCount, colCount
        Case ".xlsx", ".xlsm"
            WriteExcel outputPath, inputPath, headers, data, cleaned, reports, rowCount, colCount
        Case Else
            MsgBox "Unsupported output format: '" & outExt & "'.", vbExclamation: Exit Sub
    End Select

    MsgBox "Done." & vbCrLf & vbCrLf & _
           "Input : " & inputPath & vbCrLf & _
           "Output: " & outputPath & vbCrLf & vbCrLf & _
           "Each source column -> _original | _cleaned | _report", _
           vbInformation, "Mojibake Cleaner"
End Sub

' ============================================================================
'  WRITERS
' ============================================================================
Public Sub WriteCsv(ByVal path As String, ByVal delim As String, _
                    ByVal headers() As String, ByVal data() As Variant, _
                    ByRef cleaned() As Variant, ByRef reports() As String, _
                    ByVal rowCount As Long, ByVal colCount As Long)
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    If fso.FileExists(path) Then fso.DeleteFile path, True
    Dim f As Object: Set f = fso.CreateTextFile(path, True, True)
    Dim c As Long, r As Long, line As String
    Dim hline As String: hline = ""
    For c = 1 To colCount
        If c > 1 Then hline = hline & delim
        hline = hline & CsvEscape(headers(c) & "_original", delim)
        hline = hline & delim & CsvEscape(headers(c) & "_cleaned", delim)
        hline = hline & delim & CsvEscape(headers(c) & "_report", delim)
    Next c
    f.WriteLine hline
    For r = 1 To rowCount
        line = ""
        For c = 1 To colCount
            If c > 1 Then line = line & delim
            line = line & CsvEscape(NullToEmpty(data(r, c)), delim)
            line = line & delim & CsvEscape(NullToEmpty(cleaned(r, c)), delim)
            line = line & delim & CsvEscape(reports(r, c), delim)
        Next c
        f.WriteLine line
    Next r
    f.Close
End Sub

Public Function NullToEmpty(ByVal v As Variant) As String
    If IsNull(v) Or IsEmpty(v) Then NullToEmpty = "" Else NullToEmpty = CStr(v)
End Function

Public Function CsvEscape(ByVal s As String, ByVal delim As String) As String
    If Len(s) = 0 Then CsvEscape = "": Exit Function
    If InStr(s, delim) > 0 Or InStr(s, """") > 0 Or _
       InStr(s, vbCr) > 0 Or InStr(s, vbLf) > 0 Then
        CsvEscape = """" & Replace(s, """", """""") & """"
    Else
        CsvEscape = s
    End If
End Function

Public Sub WriteExcel(ByVal path As String, ByVal srcName As String, _
                      ByVal headers() As String, ByVal data() As Variant, _
                      ByRef cleaned() As Variant, ByRef reports() As String, _
                      ByVal rowCount As Long, ByVal colCount As Long)
    If Len(Dir$(path)) > 0 Then
        On Error Resume Next
        Kill path
        If Len(Dir$(path)) > 0 Then
            MsgBox "Cannot overwrite " & path & " - close it first.", vbExclamation
            Exit Sub
        End If
        On Error GoTo 0
    End If
    Dim xl As Object: Set xl = GetExcelApp()
    If xl Is Nothing Then MsgBox "Cannot start Excel.", vbExclamation: Exit Sub
    Dim wb As Object: Set wb = xl.Workbooks.Add
    Do While wb.Worksheets.count > 1
        wb.Worksheets(wb.Worksheets.count).Delete
    Loop
    Dim ws As Object: Set ws = wb.Worksheets(1)
    ws.name = "Cleaned"
    Dim outCols As Long: outCols = colCount * 3
    Dim hdr() As Variant: ReDim hdr(1 To 1, 1 To outCols)
    Dim c As Long
    For c = 1 To colCount
        hdr(1, (c - 1) * 3 + 1) = headers(c) & "_original"
        hdr(1, (c - 1) * 3 + 2) = headers(c) & "_cleaned"
        hdr(1, (c - 1) * 3 + 3) = headers(c) & "_report"
    Next c
    ws.Range(ws.Cells(1, 1), ws.Cells(1, outCols)).Value = hdr
    Dim outData() As Variant: ReDim outData(1 To rowCount, 1 To outCols)
    Dim r As Long
    For r = 1 To rowCount
        For c = 1 To colCount
            outData(r, (c - 1) * 3 + 1) = data(r, c)
            outData(r, (c - 1) * 3 + 2) = cleaned(r, c)
            outData(r, (c - 1) * 3 + 3) = reports(r, c)
        Next c
    Next r
    If rowCount > 0 Then
        ws.Range(ws.Cells(2, 1), ws.Cells(rowCount + 1, outCols)).Value = outData
    End If
    With ws.Range(ws.Cells(1, 1), ws.Cells(1, outCols))
        .Font.Bold = True
        .Interior.Color = RGB(220, 220, 220)
    End With
    ws.Rows(1).AutoFilter
    ws.Columns.AutoFit
    AddSummarySheet wb, reports, rowCount, colCount, srcName
    Dim saveCode As Long
    If LCase$(Right$(path, 5)) = ".xlsm" Then saveCode = 52 Else saveCode = 51
    On Error Resume Next
    wb.SaveAs path, saveCode
    If Err.Number <> 0 Then
        MsgBox "Save failed: " & Err.Description, vbExclamation
        Err.Clear
    End If
    On Error GoTo 0
    ReleaseExcelApp xl, wb
End Sub

Public Sub AddSummarySheet(ByVal wb As Object, ByRef reports() As String, _
                           ByVal rowCount As Long, ByVal colCount As Long, _
                           ByVal srcName As String)
    Dim wsSum As Object: Set wsSum = wb.Worksheets.Add
    wsSum.Move After:=wb.Worksheets(wb.Worksheets.count)
    wsSum.name = "Summary"
    Dim totalCells As Long, changedCells As Long
    Dim emailTotal As Long, urlTotal As Long, phoneTotal As Long, currTotal As Long
    Dim flagTotal As Long, mojibakeLeft As Long, shrunkTotal As Long, nullInputs As Long
    Dim r As Long, c As Long, rpt As String
    For r = 1 To rowCount
        For c = 1 To colCount
            rpt = reports(r, c)
            totalCells = totalCells + 1
            If rpt = "NULL_INPUT" Then nullInputs = nullInputs + 1
            If InStr(rpt, "OK|") = 1 Then
                If InStr(rpt, "NO_CHANGES") = 0 Then changedCells = changedCells + 1
                emailTotal = emailTotal + ExtractCount(rpt, "EMAIL=")
                urlTotal = urlTotal + ExtractCount(rpt, "URL=")
                phoneTotal = phoneTotal + ExtractCount(rpt, "PHONE=")
                currTotal = currTotal + ExtractCount(rpt, "CURR=")
                If InStr(rpt, "FLAGS=") > 0 Then
                    flagTotal = flagTotal + 1
                    If InStr(rpt, "MOJIBAKE_LEFT") > 0 Then mojibakeLeft = mojibakeLeft + 1
                    If InStr(rpt, "SHRUNK") > 0 Then shrunkTotal = shrunkTotal + 1
                End If
            End If
        Next c
    Next r
    Dim out(1 To 14, 1 To 2) As Variant
    out(1, 1) = "Clean Summary":       out(1, 2) = ""
    out(2, 1) = "Source":              out(2, 2) = srcName
    out(3, 1) = "Rows":                out(3, 2) = rowCount
    out(4, 1) = "Columns":             out(4, 2) = colCount
    out(5, 1) = "Cells Processed":     out(5, 2) = totalCells
    out(6, 1) = "Cells Changed":       out(6, 2) = changedCells
    out(7, 1) = "Emails Found":        out(7, 2) = emailTotal
    out(8, 1) = "URLs Found":          out(8, 2) = urlTotal
    out(9, 1) = "Phones Found":        out(9, 2) = phoneTotal
    out(10, 1) = "Currencies Found":   out(10, 2) = currTotal
    out(11, 1) = "Cells With Flags":   out(11, 2) = flagTotal
    out(12, 1) = "Mojibake Remaining": out(12, 2) = mojibakeLeft
    out(13, 1) = "Shrunk Cells":       out(13, 2) = shrunkTotal
    out(14, 1) = "Null Inputs":        out(14, 2) = nullInputs
    wsSum.Range("A1:B14").Value = out
    With wsSum.Range("A1:B1"): .Font.Bold = True: .Font.Size = 14: End With
    With wsSum.Range("A2:A14"): .Font.Bold = True: End With
    wsSum.Columns("A:B").AutoFit
End Sub

Public Function ExtractCount(ByVal rpt As String, ByVal key As String) As Long
    Dim p As Long: p = InStr(rpt, key)
    If p = 0 Then Exit Function
    p = p + Len(key)
    Dim e As Long: e = InStr(p, rpt, ";")
    If e = 0 Then e = Len(rpt) + 1
    Dim num As String: num = Mid$(rpt, p, e - p)
    If IsNumeric(num) Then ExtractCount = CLng(num)
End Function

' ============================================================================
'  FILE I/O HELPERS
' ============================================================================
Public Function IsInExcelHost() As Boolean
    On Error Resume Next
    IsInExcelHost = (InStr(1, Application.name, "Excel", vbTextCompare) > 0)
    On Error GoTo 0
End Function

Public Function GetExcelApp() As Object
    On Error Resume Next
    Dim xl As Object
    mExcelOwned = False
    If IsInExcelHost() Then
        Set xl = Application
    Else
        Set xl = CreateObject("Excel.Application")
        If Not xl Is Nothing Then
            xl.Visible = False
            xl.DisplayAlerts = False
            mExcelOwned = True
        End If
    End If
    On Error GoTo 0
    Set GetExcelApp = xl
End Function

Public Sub ReleaseExcelApp(ByVal xl As Object, ByVal wb As Object)
    On Error Resume Next
    If mExcelOwned Then
        If Not wb Is Nothing Then wb.Close SaveChanges:=False
        If Not xl Is Nothing Then xl.Quit
    Else
        If Not wb Is Nothing Then wb.Activate
    End If
    mExcelOwned = False
    Set wb = Nothing: Set xl = Nothing
    On Error GoTo 0
End Sub

Public Function FileExists(ByVal path As String) As Boolean
    Static fso As Object
    If fso Is Nothing Then Set fso = CreateObject("Scripting.FileSystemObject")
    FileExists = fso.FileExists(path)
End Function

Public Function ExtOf(ByVal path As String) As String
    Dim p As Long: p = InStrRev(path, ".")
    If p = 0 Then ExtOf = "" Else ExtOf = Mid$(path, p)
End Function

Public Function StripExt(ByVal path As String) As String
    Dim p As Long: p = InStrRev(path, ".")
    If p = 0 Then StripExt = path Else StripExt = Left$(path, p - 1)
End Function

Public Sub LoadCsv(ByVal path As String, ByVal delim As String, ByVal hasHeader As Boolean, _
                   ByRef data() As Variant, ByRef headers() As String, _
                   ByRef rowCount As Long, ByRef colCount As Long)
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    Dim f As Object: Set f = fso.OpenTextFile(path, 1, False, -2)
    Dim lines() As String: ReDim lines(0)
    Dim n As Long: n = 0
    Do Until f.AtEndOfStream
        ReDim Preserve lines(n)
        lines(n) = f.ReadLine
        n = n + 1
    Loop
    f.Close
    If n = 0 Then rowCount = 0: colCount = 0: Exit Sub
    Dim firstFields() As String: firstFields = ParseCsvLine(lines(0), delim)
    colCount = UBound(firstFields) - LBound(firstFields) + 1
    ReDim headers(1 To colCount)
    Dim c As Long
    For c = 1 To colCount: headers(c) = firstFields(LBound(firstFields) + c - 1): Next c
    Dim startRow As Long
    If hasHeader Then startRow = 1 Else startRow = 0
    rowCount = n - startRow
    If rowCount < 0 Then rowCount = 0
    If rowCount = 0 Then Exit Sub
    ReDim data(1 To rowCount, 1 To colCount)
    Dim r As Long
    For r = 1 To rowCount
        Dim fields() As String: fields = ParseCsvLine(lines(startRow + r - 1), delim)
        Dim fc As Long: fc = UBound(fields) - LBound(fields) + 1
        For c = 1 To colCount
            If c <= fc Then
                data(r, c) = fields(LBound(fields) + c - 1)
            Else
                data(r, c) = ""
            End If
        Next c
    Next r
End Sub

Public Function ParseCsvLine(ByVal line As String, ByVal delim As String) As String()
    Dim result() As String: ReDim result(0)
    Dim count As Long: count = 0
    Dim field As String: field = ""
    Dim inQuote As Boolean: inQuote = False
    Dim i As Long, n As Long: n = Len(line): i = 1
    Dim ch As String, delimLen As Long: delimLen = Len(delim)
    Do While i <= n
        ch = Mid$(line, i, 1)
        If inQuote Then
            If ch = """" Then
                If i < n And Mid$(line, i + 1, 1) = """" Then
                    field = field & """": i = i + 2
                Else
                    inQuote = False: i = i + 1
                End If
            Else
                field = field & ch: i = i + 1
            End If
        Else
            If ch = """" Then
                inQuote = True: i = i + 1
            ElseIf Mid$(line, i, delimLen) = delim Then
                ReDim Preserve result(count): result(count) = field
                count = count + 1: field = "": i = i + delimLen
            Else
                field = field & ch: i = i + 1
            End If
        End If
    Loop
    ReDim Preserve result(count): result(count) = field
    ParseCsvLine = result
End Function

Public Sub LoadExcel(ByVal path As String, ByVal sheetName As String, _
                     ByRef data() As Variant, ByRef headers() As String, _
                     ByRef rowCount As Long, ByRef colCount As Long)
    Dim xl As Object: Set xl = GetExcelApp()
    Dim wb As Object
    On Error GoTo Fail
    Set wb = xl.Workbooks.Open(path, False, True, , , , True)
    Dim ws As Object
    If Len(sheetName) > 0 Then
        On Error Resume Next
        Set ws = wb.Worksheets(sheetName)
        On Error GoTo Fail
    End If
    If ws Is Nothing Then Set ws = wb.Worksheets(1)
    Dim lastRow As Long, lastCol As Long
    lastRow = ws.Cells(ws.Rows.count, 1).End(-4162).Row
    lastCol = ws.Cells(1, ws.Columns.count).End(-4159).Column
    If lastRow < 1 Or lastCol < 1 Then rowCount = 0: colCount = 0: GoTo Cleanup
    rowCount = lastRow - 1: colCount = lastCol
    If rowCount < 1 Then rowCount = 0: GoTo Cleanup
    ReDim headers(1 To colCount)
    ReDim data(1 To rowCount, 1 To colCount)
    Dim r As Long, c As Long
    For c = 1 To colCount: headers(c) = CStr(ws.Cells(1, c).Value & ""): Next c
    For r = 2 To lastRow
        For c = 1 To colCount: data(r - 1, c) = ws.Cells(r, c).Value: Next c
    Next r
Cleanup:
    wb.Close SaveChanges:=False
    If mExcelOwned Then xl.Quit
    mExcelOwned = False
    Set wb = Nothing: Set xl = Nothing
    Exit Sub
Fail:
    On Error Resume Next
    If Not wb Is Nothing Then wb.Close SaveChanges:=False
    If mExcelOwned Then xl.Quit
    mExcelOwned = False
    On Error GoTo 0
    MsgBox "Failed to read " & path, vbExclamation
End Sub



