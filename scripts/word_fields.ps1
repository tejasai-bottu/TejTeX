param(
    [Parameter(Mandatory = $true)][string]$File,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = "Stop"
$before = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$word = New-Object -ComObject Word.Application
$after = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$mine = @($after | Where-Object { $before -notcontains $_ })
if ($mine.Count -eq 0) {
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    "Word attached to an instance that was already running; nothing was checked"
    exit 2
}

function Fields($doc) {
    @(foreach ($f in $doc.Fields) { "$("$($f.Code.Text)".Trim()) = $("$($f.Result.Text)".Trim())" })
}

function Heads($doc) {
    @(foreach ($p in $doc.Paragraphs) {
        if ($p.OutlineLevel -lt 10) { "$($p.Range.ListFormat.ListString)|$("$($p.Range.Text)".Trim())" }
    })
}

function Find($doc, $text) {
    foreach ($p in $doc.Paragraphs) {
        if ("$($p.Range.Text)" -like $text) { return $p }
    }
    throw "paragraph not found: $text"
}

function Add($word, $doc, $p, $style, $parts) {
    $p.Range.InsertParagraphAfter()
    $q = $p.Next()
    $k = $style
    $q.Style = $doc.Styles.Item([ref]$k)
    $q.Range.Select()
    $word.Selection.Collapse(1)
    foreach ($x in $parts) {
        if ($x.StartsWith("=")) {
            [void]$word.Selection.Fields.Add($word.Selection.Range, -1, $x.Substring(1), $false)
        } else {
            $word.Selection.TypeText($x)
        }
    }
    , $q
}

$r = [ordered]@{ file = (Split-Path $File -Leaf) }
$path = Join-Path $env:TEMP ("tejtex-word-fields-" + $r.file)
$doc = $null
try {
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    Copy-Item -LiteralPath (Resolve-Path $File).Path -Destination $path -Force
    $doc = $word.Documents.Open($path, $false, $false, $false)
    $r.repaired = $doc.ActiveWindow.Caption -like "*Repaired*"
    $r.cached = Fields $doc
    $r.update_errors = $doc.Fields.Update()
    $r.updated = Fields $doc
    $r.unchanged = (($r.cached -join "`n") -eq ($r.updated -join "`n"))
    $r.headings = Heads $doc
    $new = @(
        (Add $word $doc (Find $doc "Field Test*") -2 @("Inserted chapter")),
        (Add $word $doc (Find $doc "One*") -1 @("x = y (", "=STYLEREF 2 \w", ".", "=SEQ Equation \* ARABIC \s 2", ")")),
        (Add $word $doc (Find $doc "\begin{equation}?a*") -1 @("Theorem ", "=STYLEREF 1 \w", ".", "=SEQ theorem \* ARABIC \s 1", ". Inserted.")),
        (Add $word $doc (Find $doc "Note.*") -35 @("Figure ", "=STYLEREF 1 \w", ".", "=SEQ Figure \* ARABIC \s 1", ": Inserted figure")),
        (Add $word $doc (Find $doc "\begin{equation}?c*") -3 @("Inserted section"))
    )
    $r.update_errors_after = $doc.Fields.Update()
    $r.after_one_pass = Fields $doc
    [void]$doc.Fields.Update()
    $r.after = Fields $doc
    $r.headings_after = Heads $doc
    $r.inserted = @(foreach ($q in $new) { "$($q.Range.ListFormat.ListString)|$("$($q.Range.Text)".Trim())" })
    $r.refs_resolve = @(foreach ($f in $doc.Fields) {
        if ($f.Type -eq 3) {
            $name = "$($f.Code.Text)".Trim().Split(" ")[1]
            if (-not $doc.Bookmarks.Exists($name)) { "missing $name" }
        }
    }).Count -eq 0
    $r.links_resolve = @(foreach ($h in $doc.Hyperlinks) {
        if ($h.SubAddress -and -not $doc.Bookmarks.Exists($h.SubAddress)) { "missing $($h.SubAddress)" }
    }).Count -eq 0
    $r.errors = @($r.after | Where-Object { $_ -like "*Error!*" })
    $thm = $null
    foreach ($f in $doc.Fields) { if ("$($f.Code.Text)".Trim() -eq "REF thm_one \h") { $thm = $f; break } }
    $r.thm_ref_bold = $thm.Result.Font.Bold
    $k = -1
    $r.body_bold = $doc.Styles.Item([ref]$k).Font.Bold
} catch {
    $r.error = $_.Exception.Message
} finally {
    if ($doc) {
        $no = 0
        $doc.Close([ref]$no)
    }
    Remove-Item -LiteralPath $path -ErrorAction SilentlyContinue
    $no = 0
    $word.Quit([ref]$no)
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
$r | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 $Out
"checked $($r.file)"
