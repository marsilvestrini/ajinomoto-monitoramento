{
  "procedimentos": [
    {
      "nome": "feirinha",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "branco"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "feirinha_alergenico_fs",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "laranja"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "feirinha_alergenico_critico",
      "info": [
        {"expected_macacao_color": "macacao_azul"},
        {"expected_pallet_color": "laranja"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.macacaoTracker.statusPassoMacacao, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.macacaoTracker.alertPassoMacacao + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "feirinha_activa",
      "info": [
        {"expected_macacao_color": "macacao_azul"},
        {"expected_pallet_color": "amarelo"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.macacaoTracker.statusPassoMacacao, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.macacaoTracker.alertPassoMacacao + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    }, 
    {
      "nome": "pallet_fechado",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "branco"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "pallet_fechado_alergenico_fs",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "laranja"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch,self.finishTracker.statusPassoFinish, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "palett_fechado_alergenico_critico",
      "info": [
        {"expected_macacao_color": "macacao_azul"},
        {"expected_pallet_color": "laranja"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.macacaoTracker.statusPassoMacacao, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.macacaoTracker.alertPassoMacacao + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "pallet_fechado_activa",
      "info": [
        {"expected_macacao_color": "macacao_azul"},
        {"expected_pallet_color": "amarelo"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.macacaoTracker.statusPassoMacacao, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.macacaoTracker.alertPassoMacacao + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "balde_galao",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "branco"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "balde_galao_fs",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "laranja"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "palete_fechado_mole",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "branco"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
      "nome": "material_unico",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "branco"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacoteTracker, self.stretchTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.palletTracker.statusPassoCollor, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish, None, None]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.palletTracker.alertPassoCollor + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    },
    {
    "nome": "polpa",
      "info": [
        {"expected_macacao_color": "macacao_branco"},
        {"expected_pallet_color": "verde_polpa"},
        {"expected_pallet_class": "pallet_descoberto"}
      ],
      "ordem": "[self.startTracker, self.macacaoTracker, self.palletTracker, self.pacotePolpaTracker,self.labelPolpaTracker, self.finishTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.macacaoTracker.statusPassoMacacao, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacotePolpaTracker.statusPassoPacotePolpa, self.labelPolpaTracker.statusPassoLabelPolpa, self.finishTracker.statusPassoFinish]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.macacaoTracker.alertPassoMacacao + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacotePolpaTracker.alertsPassoPacotePolpa + self.labelPolpaTracker.alertPassoLabelPolpa + self.finishTracker.alertPassoFinish"
    },
    {
    "nome": "teste",
      "info": [
        {"expected_macacao_color": "macacao_azul"},
        {"expected_pallet_color": "amarelo"},
        {"expected_pallet_class": "pallet_coberto"}
      ],
      "ordem": "[self.pacoteTracker]",
      "db_command_etapas": "[self.startTracker.statusPassoStart, self.macacaoTracker.statusPassoMacacao, self.palletTracker.statusPassoCollor, self.palletTracker.statusPassoClassePallet, self.pacoteTracker.statusPassoProduto, self.stretchTracker.statusPassoStretch, self.finishTracker.statusPassoFinish]",
      "db_command_alertas": "self.startTracker.alertPassoStart + self.macacaoTracker.alertPassoMacacao + self.palletTracker.alertPassoCollor + self.palletTracker.alertPassoClassePallet + self.pacoteTracker.alertPassoProduto + self.stretchTracker.alertPassoStretch + self.finishTracker.alertPassoFinish"
    }
  ],

  "timeouts": [
    {
      "spectingStart": 100,
      "spectingMacacao": 100,
      "spectingPalletColor": 120,
      "spectingPalletClass": 120,
      "spectingStrech": 180,
      "spectingPacotes": 1200,
      "spectingFinish" : 180,
      "spectingLabelPolpa": 120

    }
  ],

  "required_times": [
    {
      "spectingStrech": 25,
      "spectingPacotes": 15, 
      "spectingStart": 5,
      "spectingFinish": 5,
      "spectingMacacao": 10,
      "spectingPalletColor": 5,
      "spectingPalletClass": 5,
      "spectingLabelPolpa": 5,
      "presença_polpa": 5,
      "ausencia_polpa": 5
    }
  ]
}