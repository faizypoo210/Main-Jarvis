# Shared synthetic POST /api/v1/approvals body for operator scripts (ApprovalCreate).
# Canonical contract: services/control-plane/app/schemas/approvals.py
# Coordinator-style reference: coordinator/coordinator.py (requires_approval branch).

$script:ApprovalCreateSchemaDoc = 'services/control-plane/app/schemas/approvals.py'

function Get-ApprovalRequestedViaAllowedSet {
    return @('voice', 'command_center', 'system', 'sms')
}

function Get-ApprovalRiskClassAllowedSet {
    return @('green', 'amber', 'red')
}

function New-SyntheticApprovalCreatePayload {
    <#
    .SYNOPSIS
      Build the standard operator synthetic approval body (same field set for 13 and 15).
    #>
    param(
        [Parameter(Mandatory)][string]$MissionId,
        [Parameter(Mandatory)][string]$CommandText,
        [Parameter(Mandatory)][string]$ActionType,
        [Parameter(Mandatory)][string]$Reason,
        [Parameter(Mandatory)][string]$RequestedBy,
        [string]$RequestedVia = 'command_center',
        [string]$RiskClass = 'amber'
    )
    return [ordered]@{
        mission_id    = $MissionId
        action_type   = $ActionType
        risk_class    = $RiskClass
        reason        = $Reason
        command_text  = $CommandText
        requested_by  = $RequestedBy
        requested_via = $RequestedVia
    }
}

function Test-ApprovalCreatePayload {
    <#
    .SYNOPSIS
      Local guardrail: required fields and allowed enums before POST /approvals.
    #>
    param($Payload)
    $errs = @()
    $ref = "ApprovalCreate ($($script:ApprovalCreateSchemaDoc)); requested_via in { voice, command_center, system, sms }; risk_class in { green, amber, red }; see scripts/lib/ApprovalPayloadContract.ps1"
    $allowedVia = Get-ApprovalRequestedViaAllowedSet
    $allowedRisk = Get-ApprovalRiskClassAllowedSet
    if ($null -eq $Payload) {
        return @{ Valid = $false; Errors = @('payload is null'); ContractRef = $ref }
    }
    $mid = $Payload['mission_id']
    if ([string]::IsNullOrWhiteSpace([string]$mid)) {
        $errs += 'mission_id is required'
    }
    else {
        try {
            [void][guid]::Parse($mid.ToString())
        }
        catch {
            $errs += 'mission_id must be a valid UUID string'
        }
    }
    if ([string]::IsNullOrWhiteSpace([string]$Payload['action_type'])) {
        $errs += 'action_type is required'
    }
    $rc = [string]$Payload['risk_class']
    if ([string]::IsNullOrWhiteSpace($rc)) {
        $errs += 'risk_class is required'
    }
    elseif ($allowedRisk -notcontains $rc) {
        $errs += "risk_class must be one of: $($allowedRisk -join ', ')"
    }
    if ([string]::IsNullOrWhiteSpace([string]$Payload['requested_by'])) {
        $errs += 'requested_by is required'
    }
    $rv = [string]$Payload['requested_via']
    if ([string]::IsNullOrWhiteSpace($rv)) {
        $errs += 'requested_via is required'
    }
    elseif ($allowedVia -notcontains $rv) {
        $errs += "requested_via must be one of: $($allowedVia -join ', ')"
    }
    if ([string]::IsNullOrWhiteSpace([string]$Payload['command_text'])) {
        $errs += 'command_text is required for synthetic operator scripts (matches coordinator-style approval requests)'
    }
    return @{ Valid = ($errs.Count -eq 0); Errors = $errs; ContractRef = $ref }
}

function ConvertTo-ApprovalCreateJson {
    param([hashtable]$Payload)
    return $Payload | ConvertTo-Json -Compress -Depth 4
}
