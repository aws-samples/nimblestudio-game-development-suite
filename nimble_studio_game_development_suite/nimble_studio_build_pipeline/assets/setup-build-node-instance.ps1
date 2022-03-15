<powershell>
$ErrorActionPreference = "Stop"

try {
    
    $ff_url = "https://www.7-zip.org/a/7z1900-x64.msi"
    $wc = New-Object net.webclient
    $output = "C:\\7zip.msi"        
    $wc.Downloadfile($ff_url, $output)
    $logFile = "C:\\7zip.log"
    Start-Process msiexec.exe -Wait -ArgumentList "/I $output /quiet /norestart /L*v $logFile"

    
    $url = "https://d3pxv6yz143wms.cloudfront.net/11.0.3.7.1/amazon-corretto-11.0.3.7.1-1-windows-x64.msi"
    $output = "C:\\amazon-corretto.msi"
    (New-Object System.Net.WebClient).DownloadFile($url, $output)
    $logFile = "C:\\corretto.log"
    Start-Process msiexec.exe -Wait -ArgumentList "/I $output /quiet /norestart /L*v $logFile"
    
    [Environment]::SetEnvironmentVariable("JAVA_HOME", "C:\\Program Files\\Amazon Corretto\\jdk11.0.3_7")
    [System.Environment]::SetEnvironmentVariable("PATH", $Env:Path + ";$($Env:JAVA_HOME)\\bin", "User")
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

    [Environment]::SetEnvironmentVariable("ARTIFACT_BUCKET", "ARTIFACT_BUCKET_ARN_PLACEHOLDER")

    New-Item -Path "C:\\init-complete.txt" -ItemType File
  } catch [Exception] {
    echo $_.Exception.Message > exception.txt
  }
</powershell>
<persist>true</persist>