param(
    [Parameter(Mandatory = $true)][string]$Out,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Files
)
$ErrorActionPreference = "Stop"
$before = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$word = New-Object -ComObject Word.Application
$after = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$mine = @($after | Where-Object { $before -notcontains $_ }).Count -gt 0
if (-not $mine) {
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    "Word attached to an instance that was already running; nothing was checked"
    exit 2
}
$report = @()
try {
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    foreach ($f in $Files) {
        $path = (Resolve-Path $f).Path
        $r = [ordered]@{ file = (Split-Path $path -Leaf) }
        $doc = $null
        try {
            $doc = $word.Documents.Open($path, $false, $true, $false)
            $r.opened = $true
            $r.protection = $doc.ProtectionType
            $r.paragraphs = $doc.Paragraphs.Count
            $r.headings = @(foreach ($p in $doc.Paragraphs) { if ($p.OutlineLevel -lt 10) { "$($p.OutlineLevel) $("$($p.Range.Text)".Trim())" } })
            $r.lists = @(foreach ($p in $doc.Paragraphs) {
                $lf = $p.Range.ListFormat
                if ($lf.ListType -ne 0) {
                    $ls = $lf.ListString
                    $codes = ($ls.ToCharArray() | ForEach-Object { "U+{0:X4}" -f [int]$_ }) -join " "
                    "$ls [$codes] | $($p.Range.Text.Trim())"
                }
            })
            $k = -35
            $cap = $doc.Styles.Item([ref]$k).NameLocal
            $r.captions = @(foreach ($p in $doc.Paragraphs) { if ($p.Style.NameLocal -eq $cap) { $p.Range.Text.Trim() } })
            $r.tables = @(foreach ($t in $doc.Tables) {
                $head = "n/a"
                try { $head = $t.Rows.Item(1).HeadingFormat } catch {
                    $t.Range.Cells.Item(1).Select()
                    $head = $word.Selection.Rows.HeadingFormat
                }
                [ordered]@{
                    rows = $t.Rows.Count; columns = $t.Columns.Count; cells = $t.Range.Cells.Count; uniform = $t.Uniform
                    header = $head; nested = $t.Tables.Count
                    pages = "$($t.Range.Cells.Item(1).Range.Information(3))-$($t.Range.Information(3))"
                }
            })
            $r.pictures = @(foreach ($s in $doc.InlineShapes) { "$([math]::Round($s.Width, 1))x$([math]::Round($s.Height, 1))" })
            if ($doc.InlineShapes.Count -gt 0) {
                $s = $doc.InlineShapes.Item(1)
                $s.LockAspectRatio = -1
                $h0 = $s.Height
                $s.Width = $s.Width / 2
                $r.resized = [math]::Abs($s.Height - $h0 / 2) -lt 1
                $sh = $s.ConvertToShape()
                $sh.Left = 100
                $r.moved = [math]::Abs($sh.Left - 100) -lt 1
            }
            $r.bookmarks = @(foreach ($b in $doc.Bookmarks) { "$($b.Name) = $("$($b.Range.Text)".Trim())" })
            $r.links = @(foreach ($h in $doc.Hyperlinks) {
                if ($h.SubAddress) {
                    $name = $h.SubAddress
                    $ok = $doc.Bookmarks.Exists($name)
                    $landed = $false
                    if ($ok) {
                        $h.Follow()
                        $landed = $word.Selection.Start -eq $doc.Bookmarks.Item([ref]$name).Range.Start
                    }
                    "internal $name exists=$ok landed=$landed text=$($h.TextToDisplay)"
                } else {
                    "external $($h.Address) text=$($h.TextToDisplay)"
                }
            })
            $target = $null
            foreach ($p in $doc.Paragraphs) {
                if ("$($p.Range.Text)".Trim() -eq "Third step." -and $p.Range.ListFormat.ListType -ne 0) { $target = $p.Range }
            }
            if ($target) {
                $end = $target.End - 1
                $target.SetRange($end, $end)
                $target.Select()
                $word.Selection.TypeParagraph()
                $r.enter = $word.Selection.Range.ListFormat.ListString
                $word.Selection.Range.ListFormat.ListIndent()
                $r.tab = $word.Selection.Range.ListFormat.ListString
                $word.Selection.Range.ListFormat.ListOutdent()
                $r.shift_tab = $word.Selection.Range.ListFormat.ListString
                $r.after_enter = "$($word.Selection.Paragraphs.Item(1).Previous().Range.Text)".Trim()
            }
            foreach ($p in $doc.Paragraphs) {
                if ($p.OutlineLevel -eq 1) {
                    $k = -3
                    $p.Range.Style = $doc.Styles.Item([ref]$k)
                    $r.restyled_heading_level = $p.OutlineLevel
                    break
                }
            }
        } catch {
            $r.error = $_.Exception.Message
        } finally {
            if ($doc) {
                $no = 0
                $doc.Close([ref]$no)
            }
        }
        $report += $r
    }
} finally {
    $no = 0
    $word.Quit([ref]$no)
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
$report | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 $Out
"checked $($Files.Count) files"
