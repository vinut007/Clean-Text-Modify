' ============================================================================
' VModel VBA Advanced Cleaner (Standard Module — no Class modules needed)
' - Interactive file selection, column selection, in-place cleaning
' - Tracks errors per row and writes them to an "Errors" column
' - Fixes: mojibake, accents, invisible chars, emojis, non-ASCII, punctuation
' - Preserves emails, URLs, money, CJK scripts (optional)
' ============================================================================

Option Explicit

' ----------------------------------------------------------------------------
' USER SETTINGS
' ----------------------------------------------------------------------------
Private Const DEFAULT_SKIP_FIRST_ROW As Boolean = True
Private Const ADD_ERROR_COLUMN As Boolean = True
Private Const ERROR_COL_NAME As String = "VModel_Errors"
Private Const MAX_CELL_PREVIEW As Long = 200

' ----------------------------------------------------------------------------
' TYPES (replace classes)
' ----------------------------------------------------------------------------
Private Type CleanOptions
    FixMojibake As Boolean
    FoldAccents As Boolean
    NormalizeInvisible As Boolean
    FoldSymbols As Boolean
    CollapsePunctuation As Boolean
    KeepEmoji As Boolean
    ProtectEmailUrlMoney As Boolean
    TransliterateCJK As Boolean
End Type

Private Type CleanStats
    CellsChanged As Long
    RowsWithErrors As Long
End Type

' ----------------------------------------------------------------------------
' ENTRY POINT — run this from Alt+F8
' ----------------------------------------------------------------------------
Public Sub VModel_AdvancedClean()
    Dim wb As Workbook, ws As Worksheet, fPath As String
    Dim lastRow As Long, lastCol As Long, headerRow As Long
    Dim colNames() As String, skipCols As Collection
    Dim processCols As Collection
    Dim r As Long, c As Long, errCol As Long
    Dim cVar As Variant
    Dim originalVal As String, cleanedVal As String, errList As String
    Dim opts As CleanOptions, stats As CleanStats
    
    ' --- 1. Pick file ---
    fPath = PickFile("Select Excel/CSV file to clean")
    If fPath = "" Then Exit Sub
    
    ' --- 2. Open workbook ---
    Set wb = OpenWorkbookSafe(fPath)
    If wb Is Nothing Then Exit Sub
    Set ws = wb.ActiveSheet
    
    ' --- 3. Detect used range ---
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    If lastRow < 2 Or lastCol < 1 Then
        MsgBox "No data found (need at least 1 header row + 1 data row).", vbExclamation
        wb.Close False
        Exit Sub
    End If
    
    headerRow = IIf(DEFAULT_SKIP_FIRST_ROW, 1, 0)
    
    ' --- 4. Read column headers ---
    ReDim colNames(1 To lastCol)
    For c = 1 To lastCol
        Dim hVal As Variant
        hVal = ws.Cells(headerRow, c).Value
        If hVal <> "" Then
            colNames(c) = CStr(hVal)
        Else
            colNames(c) = "Column_" & c
        End If
    Next c
    
    ' --- 5. Ask which columns to SKIP ---
    Set skipCols = AskSkipColumns(colNames, headerRow, ws, lastRow)
    If skipCols Is Nothing Then
        wb.Close False
        Exit Sub
    End If
    
    ' --- 6. Build list of columns TO PROCESS ---
    Set processCols = New Collection
    For c = 1 To lastCol
        If Not IsInCollection(skipCols, c) Then
            processCols.Add c
        End If
    Next c
    
    If processCols.Count = 0 Then
        MsgBox "No columns selected for processing.", vbExclamation
        wb.Close False
        Exit Sub
    End If
    
    ' --- 7. Prepare error column ---
    errCol = 0
    If ADD_ERROR_COLUMN Then
        errCol = lastCol + 1
        ws.Cells(headerRow, errCol).Value = ERROR_COL_NAME
        ws.Cells(headerRow, errCol).Font.Bold = True
        ws.Columns(errCol).ColumnWidth = 40
    End If
    
    ' --- 8. Set cleaning options ---
    opts = DefaultOptions()
    
    ' --- 9. Process each row ---
    stats = NewStats()
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    Dim startRow As Long
    startRow = IIf(headerRow = 1, 2, 1)
    
    For r = startRow To lastRow
        errList = ""
        For Each cVar In processCols
            c = cVar
            originalVal = CStr(ws.Cells(r, c).Value)
            If Len(originalVal) > 0 Then
                cleanedVal = CleanTextAdvanced(originalVal, opts, errList)
                If cleanedVal <> originalVal Then
                    ws.Cells(r, c).Value = cleanedVal
                    stats.CellsChanged = stats.CellsChanged + 1
                End If
            End If
        Next cVar
        
        If ADD_ERROR_COLUMN And Len(errList) > 0 Then
            If Right(errList, 2) = ", " Then errList = Left(errList, Len(errList) - 2)
            ws.Cells(r, errCol).Value = errList
            stats.RowsWithErrors = stats.RowsWithErrors + 1
        End If
        
        If r Mod 1000 = 0 Then
            Application.StatusBar = "VModel: processing row " & r & " of " & lastRow & "..."
        End If
    Next r
    
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True
    Application.StatusBar = False
    
    ' --- 10. Save with suffix ---
    Dim savePath As String
    savePath = GetSavePath(fPath)
    wb.SaveAs savePath, xlOpenXMLWorkbook
    wb.Close False
    
    ' --- 11. Summary ---
    MsgBox "VModel Clean Complete!" & vbCrLf & vbCrLf & _
           "Rows processed: " & (lastRow - startRow + 1) & vbCrLf & _
           "Columns cleaned: " & processCols.Count & vbCrLf & _
           "Cells changed: " & stats.CellsChanged & vbCrLf & _
           "Rows with errors: " & stats.RowsWithErrors & vbCrLf & vbCrLf & _
           "Saved to: " & savePath, vbInformation, "VModel Advanced Cleaner"
End Sub

' ============================================================================
' OPTION/STATS INITIALIZERS (replace Class_Initialize)
' ============================================================================

Private Function DefaultOptions() As CleanOptions
    Dim o As CleanOptions
    o.FixMojibake = True
    o.FoldAccents = True
    o.NormalizeInvisible = True
    o.FoldSymbols = True
    o.CollapsePunctuation = True
    o.KeepEmoji = True
    o.ProtectEmailUrlMoney = True
    o.TransliterateCJK = False
    DefaultOptions = o
End Function

Private Function NewStats() As CleanStats
    Dim s As CleanStats
    s.CellsChanged = 0
    s.RowsWithErrors = 0
    NewStats = s
End Function

' ============================================================================
' FILE / COLUMN SELECTION HELPERS
' ============================================================================

Private Function PickFile(titleStr As String) As String
    Dim fd As FileDialog
    Set fd = Application.FileDialog(msoFileDialogFilePicker)
    With fd
        .Title = titleStr
        .AllowMultiSelect = False
        .Filters.Clear
        .Filters.Add "Excel Files", "*.xlsx; *.xlsm; *.xlsb; *.xls"
        .Filters.Add "CSV Files", "*.csv; *.txt"
        .Filters.Add "All Files", "*.*"
        If .Show = -1 Then
            PickFile = .SelectedItems(1)
        End If
    End With
End Function

Private Function OpenWorkbookSafe(fPath As String) As Workbook
    Dim ext As String, wb As Workbook
    ext = LCase(Right(fPath, 4))
    If ext = ".csv" Or ext = ".txt" Then
        Workbooks.OpenText Filename:=fPath, DataType:=xlDelimited, _
            TextQualifier:=xlDoubleQuote, ConsecutiveDelimiter:=False, _
            Comma:=True, Local:=True
        Set wb = ActiveWorkbook
    Else
        Set wb = Workbooks.Open(fPath, ReadOnly:=True)
    End If
    Set OpenWorkbookSafe = wb
End Function

Private Function AskSkipColumns(colNames() As String, headerRow As Long, _
                               ws As Worksheet, lastRow As Long) As Collection
    Dim msg As String, inputStr As String, nums() As String
    Dim i As Long, c As Long, colNum As Long
    Dim skipCols As New Collection
    Dim previewVal As String
    
    msg = "COLUMNS IN FILE:" & vbCrLf & vbCrLf
    For c = LBound(colNames) To UBound(colNames)
        previewVal = ""
        If lastRow > headerRow Then
            previewVal = CStr(ws.Cells(headerRow + 1, c).Value)
            If Len(previewVal) > MAX_CELL_PREVIEW Then
                previewVal = Left(previewVal, MAX_CELL_PREVIEW) & "..."
            End If
        End If
        msg = msg & c & ". " & colNames(c)
        If previewVal <> "" Then msg = msg & "  |  " & previewVal
        msg = msg & vbCrLf
    Next c
    
    msg = msg & vbCrLf & "Enter column NUMBERS to SKIP (comma-separated)." & vbCrLf & _
              "Example: 1,3,5  (skips columns 1, 3, and 5)" & vbCrLf & _
              "Leave empty to process ALL columns."
    
    inputStr = InputBox(msg, "VModel — Select Columns to SKIP", "")
    If inputStr = "" Then
        Set AskSkipColumns = New Collection
        Exit Function
    End If
    
    nums = Split(inputStr, ",")
    For i = LBound(nums) To UBound(nums)
        nums(i) = Trim(nums(i))
        If IsNumeric(nums(i)) Then
            colNum = CLng(nums(i))
            If colNum >= LBound(colNames) And colNum <= UBound(colNames) Then
                On Error Resume Next
                skipCols.Add colNum, CStr(colNum)
                On Error GoTo 0
            End If
        End If
    Next i
    
    Set AskSkipColumns = skipCols
End Function

Private Function IsInCollection(coll As Collection, key As Long) As Boolean
    On Error Resume Next
    Dim dummy As Variant
    dummy = coll(CStr(key))
    IsInCollection = (Err.Number = 0)
    On Error GoTo 0
End Function

Private Function GetSavePath(originalPath As String) As String
    Dim fso As Object, fName As String, fDir As String, fExt As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    fDir = fso.GetParentFolderName(originalPath)
    fName = fso.GetBaseName(originalPath)
    fExt = fso.GetExtensionName(originalPath)
    GetSavePath = fDir & "\" & fName & "_VModel_Cleaned." & fExt
End Function

' ============================================================================
' CORE CLEANING FUNCTION
' ============================================================================

Private Function CleanTextAdvanced(ByVal txt As String, opts As CleanOptions, _
                                   ByRef errList As String) As String
    Dim s As String, original As String
    Dim errBuf As String
    original = txt
    s = txt
    
    If Len(s) = 0 Then
        CleanTextAdvanced = s
        Exit Function
    End If
    
    If opts.ProtectEmailUrlMoney Then
        s = ProtectStructured(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.FixMojibake Then
        s = PreMojibakeFix(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.FixMojibake Then
        s = RepairMojibakeVBA(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.FixMojibake Then
        s = PostMojibakeFix(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.FoldAccents Then
        s = FoldAccentsVBA(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.FoldSymbols Then
        s = FoldSymbolsVBA(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    s = NormalizeInvisibleVBA(s, errBuf)
    If Len(errBuf) > 0 Then errList = errList & errBuf
    
    If Not opts.KeepEmoji Then
        s = RemoveEmojisVBA(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.TransliterateCJK Then
        s = TransliterateNonASCII(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.CollapsePunctuation Then
        s = CollapsePunctuationVBA(s, errBuf)
        If Len(errBuf) > 0 Then errList = errList & errBuf
    End If
    
    If opts.ProtectEmailUrlMoney Then
        s = RestoreStructured(s)
    End If
    
    CleanTextAdvanced = s
End Function

' ============================================================================
' PROTECTION — emails, URLs, money
' ============================================================================

Private Function ProtectStructured(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, re As Object, m As Object, matches As Object
    Dim placeholder As String, i As Long
    s = txt
    Set re = CreateObject("VBScript.RegExp")
    re.Global = True
    re.IgnoreCase = True
    
    ' Email
    re.Pattern = "\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
    Set matches = re.Execute(s)
    For i = matches.Count - 1 To 0 Step -1
        Set m = matches(i)
        placeholder = ChrW(&HE000) & "EMAIL" & i & ChrW(&HE001)
        s = Left(s, m.FirstIndex) & placeholder & Mid(s, m.FirstIndex + m.Length + 1)
    Next i
    
    ' URL
    re.Pattern = "https?://[^\s<>""']+"
    Set matches = re.Execute(s)
    For i = matches.Count - 1 To 0 Step -1
        Set m = matches(i)
        placeholder = ChrW(&HE000) & "URL" & i & ChrW(&HE001)
        s = Left(s, m.FirstIndex) & placeholder & Mid(s, m.FirstIndex + m.Length + 1)
    Next i
    
    ' Money
    re.Pattern = "[$€£¥₹₽₩¢¤]\s*\d[\d,.]*"
    Set matches = re.Execute(s)
    For i = matches.Count - 1 To 0 Step -1
        Set m = matches(i)
        placeholder = ChrW(&HE000) & "MONEY" & i & ChrW(&HE001)
        s = Left(s, m.FirstIndex) & placeholder & Mid(s, m.FirstIndex + m.Length + 1)
    Next i
    
    ProtectStructured = s
End Function

Private Function RestoreStructured(ByVal txt As String) As String
    Dim s As String
    s = txt
    s = Replace(s, ChrW(&HE000) & "EMAIL", "")
    s = Replace(s, ChrW(&HE000) & "URL", "")
    s = Replace(s, ChrW(&HE000) & "MONEY", "")
    s = Replace(s, ChrW(&HE001), "")
    RestoreStructured = s
End Function

' ============================================================================
' PRE-MOJIBAKE FIX
' ============================================================================

Private Function PreMojibakeFix(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, i As Long, n As Long, ch As String, out As String
    Dim fixed As Boolean
    s = txt
    n = Len(s)
    out = ""
    i = 1
    fixed = False
    
    Do While i <= n
        ch = Mid(s, i, 1)
        If ch = "â" And i + 2 <= n And Mid(s, i + 1, 1) = "€" And Mid(s, i + 2, 1) Like "[0-9]" Then
            out = out & "€"
            i = i + 3
            Do While i <= n And Mid(s, i, 1) Like "[0-9.,]"
                out = out & Mid(s, i, 1)
                i = i + 1
            Loop
            i = i - 1
            fixed = True
            errList = errList & "mojibake:â€+digit→€, "
        ElseIf ch = "â" And i + 1 <= n And Mid(s, i + 1, 1) = "€" Then
            out = out & "a"
            i = i + 2
            fixed = True
            errList = errList & "mojibake:â€→a, "
        Else
            out = out & ch
            i = i + 1
        End If
    Loop
    
    Dim pm As Object, k As Variant, arrKeys, j As Long
    Set pm = CreateObject("Scripting.Dictionary")
    pm.CompareMode = 1
    pm("â€•") = "•": pm("â„¢") = "™": pm("â€¬") = "a"
    pm("â€¦") = "...": pm("â€") = "-": pm("â€") = "-"
    pm("â€™") = "'": pm("â€œ") = """": pm("â€") = """"
    pm("â€¢") = "•": pm("â‚¬") = "€"
    
    arrKeys = pm.Keys
    For j = UBound(arrKeys) To LBound(arrKeys) Step -1
        k = arrKeys(j)
        If InStr(out, k) > 0 Then
            out = Replace(out, k, pm(k), 1, -1, 1)
            fixed = True
            errList = errList & "mojibake:" & k & "→" & pm(k) & ", "
        End If
    Next j
    
    If fixed Then PreMojibakeFix = out Else PreMojibakeFix = s
End Function

' ============================================================================
' FTfy-EQUIVALENT MOJIBAKE REPAIR
' ============================================================================

Private Function RepairMojibakeVBA(ByVal txt As String, ByRef errList As String) As String
    Dim out As String, i As Long, n As Long, ch As String
    Dim buf As String, j As Long, b() As Byte, decoded As String
    Dim fixed As Boolean
    
    n = Len(txt)
    out = ""
    i = 1
    fixed = False
    
    Do While i <= n
        ch = Mid(txt, i, 1)
        If AscW(ch) >= &H80 And AscW(ch) <= &HFF Then
            buf = ""
            j = i
            Do While j <= n
                Dim cj As String
                cj = Mid(txt, j, 1)
                If AscW(cj) >= &H80 And AscW(cj) <= &HFF Then
                    buf = buf & cj
                    j = j + 1
                Else
                    Exit Do
                End If
            Loop
            
            If Len(buf) >= 2 Then
                b = StrConv(buf, vbFromUnicode)
                On Error Resume Next
                decoded = StrConv(b, vbUnicode)
                On Error GoTo 0
                If decoded <> "" And decoded <> buf And IsPrintable(decoded) Then
                    out = out & decoded
                    i = j
                    fixed = True
                    errList = errList & "mojibake:latin1→utf8(" & Left(buf, 10) & "), "
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
    
    If fixed Then RepairMojibakeVBA = out Else RepairMojibakeVBA = txt
End Function

Private Function IsPrintable(ByVal s As String) As Boolean
    Dim i As Long, ch As String
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If AscW(ch) < 32 And ch <> vbTab And ch <> vbCr And ch <> vbLf Then
            IsPrintable = False
            Exit Function
        End If
    Next i
    IsPrintable = True
End Function

' ============================================================================
' POST-MOJIBAKE FRAGMENTS
' ============================================================================

Private Function PostMojibakeFix(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, n As Long, i As Long, ch As String, c2 As String, out As String
    Dim fixed As Boolean
    
    s = txt
    n = Len(s)
    out = ""
    i = 1
    fixed = False
    
    Do While i <= n
        ch = Mid(s, i, 1)
        If ch = "â" And i + 1 <= n And Mid(s, i + 1, 1) = "€" Then
            out = out & "a"
            i = i + 2
            fixed = True
            errList = errList & "mojibake:â€→a, "
        ElseIf ch = "Ã" And i + 1 <= n Then
            c2 = Mid(s, i + 1, 1)
            If AscW(c2) < &H80 Or AscW(c2) > &HFF Then
                out = out & "A"
                i = i + 1
                fixed = True
                errList = errList & "mojibake:Ã→A, "
            Else
                out = out & ch
                i = i + 1
            End If
        ElseIf ch = "ã" And i + 1 <= n Then
            c2 = Mid(s, i + 1, 1)
            If AscW(c2) < &H80 Or AscW(c2) > &HFF Then
                out = out & "a"
                i = i + 1
                fixed = True
                errList = errList & "mojibake:ã→a, "
            Else
                out = out & ch
                i = i + 1
            End If
        Else
            out = out & ch
            i = i + 1
        End If
    Loop
    
    If fixed Then PostMojibakeFix = out Else PostMojibakeFix = s
End Function

' ============================================================================
' ACCENT FOLDING
' ============================================================================

Private Function FoldAccentsVBA(ByVal txt As String, ByRef errList As String) As String
    Dim am As Object, ch As String * 1, i As Long, out As String
    Dim fixed As Boolean, replaced As String
    
    Set am = AccentMap
    out = ""
    fixed = False
    
    For i = 1 To Len(txt)
        ch = Mid(txt, i, 1)
        If am.Exists(ch) Then
            replaced = am(ch)
            out = out & replaced
            fixed = True
            errList = errList & "accent:" & ch & "→" & replaced & ", "
        Else
            out = out & ch
        End If
    Next i
    
    If fixed Then FoldAccentsVBA = out Else FoldAccentsVBA = txt
End Function

' ============================================================================
' SYMBOL FOLDING
' ============================================================================

Private Function FoldSymbolsVBA(ByVal txt As String, ByRef errList As String) As String
    Dim sm As Object, k As Variant, s As String, fixed As Boolean
    Set sm = SymbolMap
    s = txt
    fixed = False
    
    For Each k In sm.Keys
        If InStr(s, k) > 0 Then
            s = Replace(s, k, sm(k), 1, -1, 1)
            fixed = True
            errList = errList & "symbol:" & k & "→" & sm(k) & ", "
        End If
    Next k
    
    If fixed Then FoldSymbolsVBA = s Else FoldSymbolsVBA = txt
End Function

' ============================================================================
' INVISIBLE CHARACTER NORMALIZATION
' ============================================================================

Private Function NormalizeInvisibleVBA(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, fixed As Boolean
    s = txt
    fixed = False
    
    If InStr(s, ChrW(&HA0)) > 0 Then
        s = Replace(s, ChrW(&HA0), " ")
        fixed = True: errList = errList & "invisible:NBSP→space, "
    End If
    If InStr(s, ChrW(&H200B)) > 0 Then
        s = Replace(s, ChrW(&H200B), " ")
        fixed = True: errList = errList & "invisible:ZWSP→space, "
    End If
    If InStr(s, ChrW(&H200C)) > 0 Then
        s = Replace(s, ChrW(&H200C), "")
        fixed = True: errList = errList & "invisible:ZWNJ→remove, "
    End If
    If InStr(s, ChrW(&H200D)) > 0 Then
        s = Replace(s, ChrW(&H200D), "")
        fixed = True: errList = errList & "invisible:ZWJ→remove, "
    End If
    If InStr(s, ChrW(&HFEFF)) > 0 Then
        s = Replace(s, ChrW(&HFEFF), "")
        fixed = True: errList = errList & "invisible:BOM→remove, "
    End If
    If InStr(s, ChrW(&H2060)) > 0 Then
        s = Replace(s, ChrW(&H2060), "")
        fixed = True: errList = errList & "invisible:WJ→remove, "
    End If
    If InStr(s, ChrW(&HAD)) > 0 Then
        s = Replace(s, ChrW(&HAD), "")
        fixed = True: errList = errList & "invisible:SHY→remove, "
    End If
    
    Dim sp As Variant
    For Each sp In Array(ChrW(&H2000), ChrW(&H2001), ChrW(&H2002), ChrW(&H2003), _
                         ChrW(&H2004), ChrW(&H2005), ChrW(&H2006), ChrW(&H2007), _
                         ChrW(&H2008), ChrW(&H2009), ChrW(&H200A), ChrW(&H202F), _
                         ChrW(&H205F), ChrW(&H3000))
        If InStr(s, sp) > 0 Then
            s = Replace(s, sp, " ")
            fixed = True
            errList = errList & "invisible:space" & Hex(AscW(sp)) & "→space, "
        End If
    Next sp
    
    s = Replace(s, vbCrLf, " ")
    s = Replace(s, vbCr, " ")
    s = Replace(s, vbLf, " ")
    s = Replace(s, vbTab, " ")
    
    If fixed Then NormalizeInvisibleVBA = s Else NormalizeInvisibleVBA = txt
End Function

' ============================================================================
' EMOJI REMOVAL
' ============================================================================

Private Function RemoveEmojisVBA(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, i As Long, n As Long, ch As String, out As String
    Dim removed As Boolean, emojiCount As Long
    
    s = txt
    n = Len(s)
    out = ""
    removed = False
    emojiCount = 0
    
    For i = 1 To n
        ch = Mid(s, i, 1)
        If AscW(ch) >= &H1F300 Or (AscW(ch) >= &H2600 And AscW(ch) <= &H26FF) Then
            emojiCount = emojiCount + 1
            removed = True
        Else
            out = out & ch
        End If
    Next i
    
    If removed Then
        errList = errList & "emoji:removed " & emojiCount & " chars, "
        RemoveEmojisVBA = out
    Else
        RemoveEmojisVBA = txt
    End If
End Function

' ============================================================================
' NON-ASCII TRANSLITERATION
' ============================================================================

Private Function TransliterateNonASCII(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, i As Long, ch As String, out As String
    Dim count As Long, am As Object
    
    s = txt
    out = ""
    count = 0
    Set am = AccentMap
    
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If AscW(ch) > 127 And Not IsCJK(ch) Then
            If am.Exists(ch) Then
                out = out & am(ch)
                count = count + 1
            Else
                out = out & ch
            End If
        Else
            out = out & ch
        End If
    Next i
    
    If count > 0 Then
        errList = errList & "nonascii:transliterated " & count & " chars, "
        TransliterateNonASCII = out
    Else
        TransliterateNonASCII = txt
    End If
End Function

Private Function IsCJK(ByVal ch As String) As Boolean
    Dim cp As Long
    cp = AscW(ch)
    IsCJK = (cp >= &H4E00 And cp <= &H9FFF) Or _
            (cp >= &H3400 And cp <= &H4DBF) Or _
            (cp >= &HAC00 And cp <= &HD7AF) Or _
            (cp >= &H3040 And cp <= &H309F) Or _
            (cp >= &H30A0 And cp <= &H30FF)
End Function

' ============================================================================
' PUNCTUATION COLLAPSE
' ============================================================================

Private Function CollapsePunctuationVBA(ByVal txt As String, ByRef errList As String) As String
    Dim s As String, n As Long, i As Long, ch As String, out As String
    Dim j As Long, c2 As String, isVer As Boolean, runLen As Long, fixed As Boolean
    
    s = txt
    n = Len(s)
    out = ""
    i = 1
    fixed = False
    
    Do While i <= n
        ch = Mid(s, i, 1)
        If IsPunctChar(ch) Then
            isVer = False
            If i > 1 And i < n Then
                c2 = Mid(s, i - 1, 1)
                If c2 Like "[0-9]" Then
                    c2 = Mid(s, i + 1, 1)
                    If c2 Like "[0-9]" And (ch = "." Or ch = "/" Or ch = "-") Then
                        isVer = True
                    End If
                End If
            End If
            
            If Not isVer Then
                j = i + 1
                Do While j <= n
                    c2 = Mid(s, j, 1)
                    If IsPunctChar(c2) Or c2 Like "[0-9]" Then
                        j = j + 1
                    Else
                        Exit Do
                    End If
                Loop
                runLen = j - i
                If runLen >= 3 Then
                    out = out & ch
                    i = j
                    fixed = True
                    errList = errList & "punctuation:collapsed " & runLen & "→1, "
                End If
            End If
        End If
        out = out & ch
        i = i + 1
    Loop
    
    If fixed Then CollapsePunctuationVBA = out Else CollapsePunctuationVBA = s
End Function

' ============================================================================
' MAPS
' ============================================================================

Private Function AccentMap() As Object
    Dim m As Object
    Set m = CreateObject("Scripting.Dictionary")
    m.CompareMode = 1
    
    ' Latin-1 Supplement
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
    
    ' Latin Extended-A
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
    
    ' Vietnamese
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
    
    Set AccentMap = m
End Function

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
    Set SymbolMap = m
End Function

Private Function IsPunctChar(ByVal ch As String) As Boolean
    Dim p As String
    p = """!#$%&'()*+,-./:;<=>?@[\]^_`{|}~"
    IsPunctChar = (InStr(p, ch) > 0)
End Function

' ============================================================================
' QUICKSORT FOR KEY SORTING
' ============================================================================

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